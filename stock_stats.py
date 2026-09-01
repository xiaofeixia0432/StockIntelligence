"""股票数据库统计与趋势分析工具。

该脚本会扫描 SQLite 数据库中的股票表，汇总每张表的日期范围、记录数、
高低价差分布、跌幅分布等指标，并支持按日期、周期、图表方式进行分析。

主要用途：
- 检查数据库中有哪些股票表
- 统计表的时间覆盖范围与数据完整性
- 计算最近 N 天的趋势和跌幅
- 生成趋势报告或绘制走势图
"""

import argparse
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
except ImportError:  # pragma: no cover
    matplotlib = None
    plt = None
    font_manager = None

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(DB_DIR, "stock.db")

# ------------------------------------------------------------
# 1. SQLite 元数据读取：表名、字段名、日期字段判断
# ------------------------------------------------------------

def get_table_names(db_path: str):
    """获取数据库中所有股票表名，排除 SQLite 内部表和 stock_info。"""
    conn = sqlite3.connect(db_path)
    try:
        # sqlite_master 中保存数据库对象元信息；这里过滤掉系统表，保留真正的业务表。
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'stock_info' ORDER BY name"
        ).fetchall()
        return [row[0] for row in tables]
    finally:
        conn.close()


def _resolved_tables(db_path: str, table_name: str = None, limit: int = None):
    """返回待分析的表名列表；默认只扫描前 N 张表，避免大数据库场景卡死。"""
    if table_name:
        return [table_name]
    tables = get_table_names(db_path)
    if limit is None:
        return tables
    try:
        max_limit = int(limit)
    except (TypeError, ValueError):
        return tables
    if max_limit <= 0:
        return []
    return tables[:max_limit]


def table_has_date_column(db_path: str, table_name: str) -> bool:
    """判断某张表是否拥有 date 字段，便于过滤出可按日期分析的股票表。"""
    conn = sqlite3.connect(db_path)
    try:
        columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
        return any(column[1] == 'date' for column in columns)
    finally:
        conn.close()


def get_table_stats(db_path: str, table_name: str):
    """统计单张表的总条数、日期字段非空条数以及时间覆盖范围。"""
    conn = sqlite3.connect(db_path)
    try:
        # 1）总记录数：衡量该表的数据规模
        total_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

        # 2）有效日期记录数：排除 NULL 和空字符串，确保时间维度是可用的
        date_count = conn.execute(
            f'SELECT COUNT(*) FROM "{table_name}" WHERE date IS NOT NULL AND date != ""'
        ).fetchone()[0]

        # 3）最早和最晚日期：用于快速判断数据覆盖范围是否连续或缺失
        min_date = conn.execute(
            f'SELECT MIN(date) FROM "{table_name}" WHERE date IS NOT NULL AND date != ""'
        ).fetchone()[0]
        max_date = conn.execute(
            f'SELECT MAX(date) FROM "{table_name}" WHERE date IS NOT NULL AND date != ""'
        ).fetchone()[0]
        return {
            'table': table_name,
            'total_rows': total_count,
            'date_rows': date_count,
            'min_date': min_date,
            'max_date': max_date,
        }
    finally:
        conn.close()


# ------------------------------------------------------------
# 2. 数据库概览与按日期统计
# ------------------------------------------------------------

def summarize_stock_db(db_path: str = DEFAULT_DB_PATH, limit: int = 20):
    """输出数据库总览：默认只扫描前 N 张表，避免超大数据库性能退化。"""
    tables = _resolved_tables(db_path, limit=limit)
    stats = []
    for table in tables:
        # 仅处理真正的时间序列表，忽略没有 date 字段的辅助表或非行情数据表。
        if not table_has_date_column(db_path, table):
            continue
        stats.append(get_table_stats(db_path, table))

    if not stats:
        print('未发现带 date 字段的股票表。')
        return []

    # 汇总数据库整体规模，便于快速判断数据量是否充足。
    total_rows = sum(item['total_rows'] for item in stats)
    total_date_rows = sum(item['date_rows'] for item in stats)

    # 记录最早/最晚日期的出现次数，用于粗略检查数据的日期分布是否集中。
    date_overview = defaultdict(int)
    for item in stats:
        if item['min_date']:
            date_overview[item['min_date']] += 1
        if item['max_date']:
            date_overview[item['max_date']] += 1

    print(f'Stock DB: {db_path}')
    print(f'股票表数量: {len(stats)}')
    print(f'总记录数: {total_rows}')
    print(f'有 date 字段的记录数: {total_date_rows}')
    print('---')

    for item in stats:
        print(
            f"{item['table']:>12} | rows={item['total_rows']:>6} | date_rows={item['date_rows']:>6} | "
            f"min_date={item['min_date'] or '-'} | max_date={item['max_date'] or '-'}"
        )

    print('---')
    print('日期样例（最早/最晚）:')
    print(sorted(date_overview.items())[:10])
    return stats


def count_rows_by_date(db_path: str, target_date: str, limit: int = 200):
    """统计某一天在各股票表中有多少条记录，默认仅扫描前 N 张表。"""
    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, limit=limit)
        matches = []
        for table in tables:
            if not table_has_date_column(db_path, table):
                continue
            # 这里直接按 date = ? 查询，适合核对某个交易日是否存在缺失记录。
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE date = ?', (target_date,)
            ).fetchone()[0]
            if count > 0:
                matches.append((table, count))
        total = sum(count for _, count in matches)
        print(f'日期 {target_date} 的匹配记录总数: {total}')
        for table, count in matches:
            print(f'{table}: {count}')
        return matches
    finally:
        conn.close()


def get_recent_date_range(days: int, end_date: str = None):
    """返回最近 days 天的日期范围，包含 start_date 和 end_date。"""
    if days <= 0:
        raise ValueError('days 必须大于 0')

    # 默认以当天作为结束日期，向前回溯 days-1 天，形成一个闭区间。
    end = end_date or datetime.now().strftime('%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')
    start_dt = end_dt - timedelta(days=days - 1)
    return start_dt.strftime('%Y-%m-%d'), end


def count_rows_by_recent_days(db_path: str, days: int, end_date: str = None, limit: int = 200):
    """统计从当前日期往前 days 天（含当天）范围内，每个表的记录数。"""
    start_date, end = get_recent_date_range(days, end_date)
    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, limit=limit)
        matches = []
        for table in tables:
            if not table_has_date_column(db_path, table):
                continue
            # date >= start_date AND date <= end 用于筛选某个时间窗内的行情数据。
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE date >= ? AND date <= ?',
                (start_date, end),
            ).fetchone()[0]
            if count > 0:
                matches.append((table, count))
        total = sum(count for _, count in matches)
        print(f'时间范围 {start_date} ~ {end} 的匹配记录总数: {total}')
        for table, count in matches:
            print(f'{table}: {count}')
        return {
            'start_date': start_date,
            'end_date': end,
            'total': total,
            'matches': matches,
        }
    finally:
        conn.close()


# ------------------------------------------------------------
# 3. 周期统计：高低差、跌幅和开盘-最低价分布
# ------------------------------------------------------------

def table_has_high_low_columns(db_path: str, table_name: str) -> bool:
    """检查表是否具备 high / low 两个字段，用于高低价差分析。"""
    conn = sqlite3.connect(db_path)
    try:
        columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        names = {column[1] for column in columns}
        return 'high' in names and 'low' in names
    finally:
        conn.close()


def table_has_close_column(db_path: str, table_name: str) -> bool:
    """检查表是否存在 close 列，后续用于计算收盘价走势和跌幅。"""
    conn = sqlite3.connect(db_path)
    try:
        columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        names = {column[1] for column in columns}
        return 'close' in names
    finally:
        conn.close()


def table_has_open_column(db_path: str, table_name: str) -> bool:
    """检查表是否同时具备 open 和 low 字段，用于开盘价-最低价分析。"""
    conn = sqlite3.connect(db_path)
    try:
        columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        names = {column[1] for column in columns}
        return 'open' in names and 'low' in names
    finally:
        conn.close()


def get_period_high_and_current_close(db_path: str, table_name: str, start_date: str, end_date: str):
    """返回给定日期区间内的最高价，以及以 end_date 结尾的最新收盘价。"""
    conn = sqlite3.connect(db_path)
    try:
        # 统计区间内的峰值，供后续计算“当前价格相对周期最高价”的跌幅。
        max_high_row = conn.execute(
            f'SELECT MAX(high) FROM "{table_name}" WHERE date >= ? AND date <= ?',
            (start_date, end_date),
        ).fetchone()
        max_high = max_high_row[0] if max_high_row and max_high_row[0] is not None else None

        # 取最新收盘价；如果数据中有日期缺失，则这里自然返回最近可用的 close 值。
        latest_close_row = conn.execute(
            f'SELECT close FROM "{table_name}" WHERE date <= ? ORDER BY date DESC LIMIT 1',
            (end_date,),
        ).fetchone()
        current_close = latest_close_row[0] if latest_close_row and latest_close_row[0] is not None else None

        return max_high, current_close
    finally:
        conn.close()


def get_drop_ratio_from_period_high(db_path: str, days: int = None, end_date: str = None, table_name: str = None, limit: int = 200):
    """统计某个时间段内，当前价格相对周期最高价的跌幅比例。

    例子：若一只股票在最近 30 天内最高价 100，当前收盘价 80，那么跌幅约为 20%。
    这个函数常用于观察“相对历史峰值”的回撤强度。
    """
    if days is not None:
        start_date, end = get_recent_date_range(days, end_date)
    elif end_date is not None:
        start_date = None
        end = end_date
    else:
        raise ValueError('需提供 days 或 end_date')

    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, table_name=table_name, limit=limit)
        result = []
        for table in tables:
            if not table_has_date_column(db_path, table):
                continue
            if not table_has_close_column(db_path, table):
                continue
            if days is not None:
                # 重点：区间内的最高价 vs 结束日期时最近的收盘价。
                max_high, current_close = get_period_high_and_current_close(db_path, table, start_date, end)
            else:
                # 如果不指定 days，而只给了 end_date，则视为“截至该日期的历史最高价”。
                max_high_agg = conn.execute(
                    f'SELECT MAX(high) FROM "{table}" WHERE date <= ?', (end,)
                ).fetchone()[0]
                max_high = max_high_agg
                current_close_row = conn.execute(
                    f'SELECT close FROM "{table}" WHERE date <= ? ORDER BY date DESC LIMIT 1', (end,)
                ).fetchone()
                current_close = current_close_row[0] if current_close_row else None

            if max_high is None or current_close is None:
                continue

            max_high_val = float(max_high)
            current_close_val = float(current_close)
            # drop_rate = (peak - current) / peak，表示从高点回落的比例。
            drop_rate = 0.0 if max_high_val <= 0 else (max_high_val - current_close_val) / max_high_val

            result.append({
                'table': table,
                'period_start': start_date,
                'period_end': end,
                'max_high': max_high_val,
                'current_close': current_close_val,
                'drop_ratio': round(drop_rate, 6),
                'drop_pct': round(drop_rate * 100, 2),
            })

        result.sort(key=lambda x: x['drop_ratio'], reverse=True)
        print(f'当前股价相对周期最高价跌幅统计 | days={days} | end_date={end} | table={table_name or "all"}')
        if not result:
            print('未发现满足条件的数据。')
            return {'period_start': start_date, 'period_end': end, 'items': []}

        for item in result:
            print(
                f"{item['table']}: max_high={item['max_high']} | current_close={item['current_close']} | "
                f"drop_ratio={item['drop_ratio']:.6f} | drop_pct={item['drop_pct']}%"
            )
        return {'period_start': start_date, 'period_end': end, 'items': result}
    finally:
        conn.close()


def group_high_low_diff(db_path: str, days: int = None, end_date: str = None, step: float = 1.0, table_name: str = None, limit: int = 200):
    """按 (high - low) 的差值分组统计，按 step 作为分组宽度。

    例如 step=1.0 时，把所有振幅落在 [0,1)、[1,2)、[2,3) 等区间中的记录进行计数，
    方便看哪些波动幅度最常见。
    """
    if step <= 0:
        raise ValueError('step 必须大于 0')

    if days is not None:
        start_date, end = get_recent_date_range(days, end_date)
        date_filter = 'WHERE date >= ? AND date <= ?'
        params = (start_date, end)
    elif end_date is not None:
        date_filter = 'WHERE date <= ?'
        params = (end_date,)
    else:
        date_filter = ''
        params = ()

    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, table_name=table_name, limit=limit)
        result = []
        for table in tables:
            if not table_has_date_column(db_path, table) or not table_has_high_low_columns(db_path, table):
                continue
            rows = conn.execute(
                f'SELECT high, low FROM "{table}" {date_filter}',
                params,
            ).fetchall()

            # bucket_index = int(diff // step) 让相近的振幅落入同一“分组桶”中，
            # 从而统计每个区间内出现了多少次。
            buckets = defaultdict(int)
            for high, low in rows:
                try:
                    diff = float(high) - float(low)
                except (TypeError, ValueError):
                    continue
                bucket_index = int(diff // step)
                buckets[bucket_index] += 1

            bucket_list = []
            for bucket_index, count in sorted(buckets.items()):
                start = bucket_index * step
                end_value = (bucket_index + 1) * step
                bucket_list.append({
                    'range_start': round(start, 4),
                    'range_end': round(end_value, 4),
                    'count': count,
                })

            total = sum(item['count'] for item in bucket_list)
            if total > 0:
                result.append({
                    'table': table,
                    'period_start': start_date if days is not None else None,
                    'period_end': end if days is not None else end_date,
                    'step': step,
                    'total': total,
                    'buckets': bucket_list,
                })

        print(f'高低差分组统计 | step={step} | days={days} | end_date={end_date} | table={table_name or "all"}')
        if not result:
            print('未发现满足条件的表。')
            return {'step': step, 'total': 0, 'items': []}

        for item in result:
            print(f"{item['table']}: total={item['total']}")
            for bucket in item['buckets']:
                print(
                    f"  [{bucket['range_start']}, {bucket['range_end']}): {bucket['count']}"
                )
        return {'step': step, 'items': result}
    finally:
        conn.close()


def group_open_low_drop_distribution(db_path: str, days: int = None, end_date: str = None, step: float = 5.0, table_name: str = None, limit: int = 200):
    """按开盘价-最低价跌幅百分比分组统计，统计最近 N 天内各组出现多少次。

    例如 step=5.0 时，统计 open-low 跌幅落在 [0,5)%, [5,10)%, [10,15)% 等区间的次数。
    这样可以判断一天中开盘后回落幅度大多集中在什么范围。
    """
    if step <= 0:
        raise ValueError('step 必须大于 0')

    if days is not None:
        start_date, end = get_recent_date_range(days, end_date)
        date_filter = 'WHERE date >= ? AND date <= ?'
        params = (start_date, end)
    elif end_date is not None:
        date_filter = 'WHERE date <= ?'
        params = (end_date,)
    else:
        date_filter = ''
        params = ()

    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, table_name=table_name, limit=limit)
        result = []
        for table in tables:
            if not table_has_date_column(db_path, table) or not table_has_open_column(db_path, table):
                continue
            rows = conn.execute(
                f'SELECT open, low FROM "{table}" {date_filter}',
                params,
            ).fetchall()
            buckets = defaultdict(int)
            for open_price, low_price in rows:
                try:
                    open_val = float(open_price)
                    low_val = float(low_price)
                except (TypeError, ValueError):
                    continue
                if open_val <= 0:
                    continue
                # (open - low) / open 表示开盘后最低点相对开盘价的跌幅。
                drop_pct = ((open_val - low_val) / open_val) * 100.0
                if drop_pct < 0:
                    drop_pct = 0.0
                bucket_index = int(drop_pct // step)
                buckets[bucket_index] += 1

            bucket_list = []
            for bucket_index, count in sorted(buckets.items()):
                bucket_start = bucket_index * step
                bucket_end = (bucket_index + 1) * step
                bucket_list.append({
                    'range_start': round(bucket_start, 2),
                    'range_end': round(bucket_end, 2),
                    'count': count,
                })

            total = sum(item['count'] for item in bucket_list)
            if total <= 0:
                continue
            dominant_bucket = max(bucket_list, key=lambda x: x['count'])
            result.append({
                'table': table,
                'period_start': start_date if days is not None else None,
                'period_end': end if days is not None else end_date,
                'step': step,
                'total': total,
                'buckets': bucket_list,
                'dominant_bucket': dominant_bucket,
            })

        print(f'开盘价-最低价跌幅分组统计 | step={step}% | days={days} | end_date={end_date} | table={table_name or "all"}')
        for item in result:
            print(f"{item['table']}: total={item['total']} | dominant={item['dominant_bucket']}")
            for bucket in item['buckets']:
                print(f"  [{bucket['range_start']}, {bucket['range_end']}): {bucket['count']}")
        return {'step': step, 'items': result, 'period_start': start_date if days is not None else None, 'period_end': end if days is not None else end_date}
    finally:
        conn.close()


def plot_open_low_drop_distribution(db_path: str, days: int, end_date: str = None, step: float = 5.0, table_name: str = None, save_path: str = None):
    """绘制开盘价相对最低价跌幅分布柱状图。"""
    if plt is None:
        raise RuntimeError('未安装 matplotlib，请先执行: pip install matplotlib')
    setup_matplotlib_chinese()

    report = group_open_low_drop_distribution(db_path, days=days, end_date=end_date, step=step, table_name=table_name)
    items = report.get('items', [])
    if table_name:
        items = [item for item in items if item['table'] == table_name]
    if not items:
        print('未找到满足条件的表。')
        return []

    start_date = report.get('period_start') or ''
    end_value = report.get('period_end') or ''

    plt.figure(figsize=(12, 7))
    colors = plt.cm.tab10.colors
    for idx, item in enumerate(items):
        labels = [f"{bucket['range_start']}~{bucket['range_end']}%" for bucket in item['buckets']]
        counts = [bucket['count'] for bucket in item['buckets']]
        plt.bar(labels, counts, color=colors[idx % len(colors)], alpha=0.8, label=item['table'])

    plt.title(f'开盘价-最低价跌幅分布 ({start_date} ~ {end_value})')
    plt.xlabel('跌幅区间 (%)')
    plt.ylabel('出现次数')
    plt.grid(axis='y', alpha=0.3)
    plt.xticks(rotation=30)
    plt.legend(loc='best')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200)
        print(f'已保存图表到: {save_path}')
    else:
        plt.show()
    return items


# ------------------------------------------------------------
# 4. 最近趋势分析：按日期窗口汇总股票的走势状态
# ------------------------------------------------------------

def analyze_recent_stock_trends(db_path: str, days: int, end_date: str = None, diff_step: float = 1.0, drop_step: float = 5.0, table_name: str = None, limit: int = 200):
    """综合统计最近 N 天的行情趋势。默认只分析前 N 张表，以避免大库扫描拖死接口。"""
    if days <= 0:
        raise ValueError('days 必须大于 0')
    if diff_step <= 0 or drop_step <= 0:
        raise ValueError('diff_step 和 drop_step 必须大于 0')

    start_date, end = get_recent_date_range(days, end_date)
    conn = sqlite3.connect(db_path)
    try:
        tables = _resolved_tables(db_path, table_name=table_name, limit=limit)
        result = []
        for table in tables:
            if not table_has_date_column(db_path, table):
                continue

            # 取出指定时间范围内的数据，按日期升序逐天扫描，便于计算区间内的趋势状态。
            rows = conn.execute(
                f'SELECT date, high, low, close, open FROM "{table}" WHERE date >= ? AND date <= ? ORDER BY date',
                (start_date, end),
            ).fetchall()
            if not rows:
                continue

            diff_buckets = defaultdict(int)
            drop_buckets = defaultdict(int)
            open_low_buckets = defaultdict(int)
            period_max_high = None
            day_count = 0
            latest_close = None

            for _, high, low, close, open_price in rows:
                # 1）high - low 的波动区间，用于判断“振幅大多集中在什么范围”。
                try:
                    diff = float(high) - float(low)
                except (TypeError, ValueError):
                    continue
                diff_bucket_index = int(diff // diff_step)
                diff_buckets[diff_bucket_index] += 1
                day_count += 1

                # 2）记录期间内的最高价和最近的收盘价，用于估算相对峰值的回撤幅度。
                if high is not None:
                    try:
                        high_val = float(high)
                        if period_max_high is None or high_val > period_max_high:
                            period_max_high = high_val
                    except (TypeError, ValueError):
                        pass

                if close is not None:
                    try:
                        latest_close = float(close)
                    except (TypeError, ValueError):
                        pass

                # 3）high -> close 的跌幅分布：观察从高点回落的集中区间。
                if high is not None and close is not None:
                    try:
                        high_val = float(high)
                        close_val = float(close)
                        if high_val > 0:
                            drop_pct = (high_val - close_val) / high_val * 100
                            if drop_pct < 0:
                                drop_pct = 0.0
                            drop_bucket_index = int(drop_pct // drop_step)
                            drop_buckets[drop_bucket_index] += 1
                    except (TypeError, ValueError):
                        pass

                # 4）open -> low 的跌幅分布：反映当日开盘后是否迅速回落。
                if open_price is not None and low is not None:
                    try:
                        open_val = float(open_price)
                        low_val = float(low)
                        if open_val > 0:
                            open_low_drop_pct = ((open_val - low_val) / open_val) * 100
                            if open_low_drop_pct < 0:
                                open_low_drop_pct = 0.0
                            open_low_bucket_index = int(open_low_drop_pct // drop_step)
                            open_low_buckets[open_low_bucket_index] += 1
                    except (TypeError, ValueError):
                        pass

            if not diff_buckets and not drop_buckets and not open_low_buckets:
                continue

            best_drop_bucket = None
            best_drop_days = 0
            for bucket_index, count in sorted(drop_buckets.items()):
                if count > best_drop_days:
                    best_drop_days = count
                    best_drop_bucket = bucket_index

            open_low_dominant = None
            if open_low_buckets:
                bucket_index, count = max(open_low_buckets.items(), key=lambda item: item[1])
                open_low_dominant = {
                    'range_start': round(bucket_index * drop_step, 2),
                    'range_end': round((bucket_index + 1) * drop_step, 2),
                    'count': count,
                }

            if period_max_high is not None and latest_close is not None and period_max_high > 0:
                current_drop_ratio = (period_max_high - latest_close) / period_max_high
                current_drop_pct = current_drop_ratio * 100
            else:
                current_drop_pct = None

            drop_interval = None
            if best_drop_bucket is not None:
                lower = best_drop_bucket * drop_step
                upper = (best_drop_bucket + 1) * drop_step
                drop_interval = {'range_start': round(lower, 4), 'range_end': round(upper, 4), 'days': best_drop_days}

            diff_bucket_summary = [{
                'range_start': round(bucket_index * diff_step, 4),
                'range_end': round((bucket_index + 1) * diff_step, 4),
                'count': count,
            } for bucket_index, count in sorted(diff_buckets.items())]

            result.append({
                'table': table,
                'period_start': start_date,
                'period_end': end,
                'days': day_count,
                'max_high': period_max_high,
                'current_close': latest_close,
                'current_drop_pct': None if current_drop_pct is None else round(current_drop_pct, 2),
                'high_low_diff_buckets': diff_bucket_summary,
                'drop_range_most': drop_interval,
                'open_low_drop_dominant': open_low_dominant,
            })

        print(f'综合分析 | 最近 {days} 天 | 结束日期 {end} | table={table_name or "all"}')
        if not result:
            print('未发现满足条件的数据。')
            return {'period_start': start_date, 'period_end': end, 'items': []}

        for item in result:
            print(f"{item['table']}: days={item['days']} | current_drop_pct={item['current_drop_pct']}% | "
                  f"most_drop_range={item['drop_range_most']} | open_low_dominant={item['open_low_drop_dominant']}")
        return {'period_start': start_date, 'period_end': end, 'items': result}
    finally:
        conn.close()


def format_recent_trends_report(report):
    """将分析结果按表格形式打印，便于快速对比不同股票的当前状态。"""
    items = report.get('items', [])
    if not items:
        print('没有可展示的趋势数据。')
        return

    headers = [
        '表名', '日期范围', '天数', '当前跌幅%', '最常跌幅区间', '区间天数', '最高价', '当前价'
    ]
    rows = []
    for item in items:
        range_text = f"{item['period_start']}~{item['period_end']}"
        drop_range = item.get('drop_range_most')
        most_drop = '-' if drop_range is None else f"{drop_range['range_start']}~{drop_range['range_end']}"
        most_days = '-' if drop_range is None else drop_range['days']
        rows.append([
            item['table'],
            range_text,
            item['days'],
            item['current_drop_pct'] if item['current_drop_pct'] is not None else '-',
            most_drop,
            most_days,
            item['max_high'] if item['max_high'] is not None else '-',
            item['current_close'] if item['current_close'] is not None else '-',
        ])

    col_widths = [max(len(str(header)), *(len(str(row[idx])) for row in rows)) for idx, header in enumerate(headers)]
    def fmt_line(parts):
        return ' | '.join(str(p).ljust(col_widths[i]) for i, p in enumerate(parts))

    print(fmt_line(headers))
    print('-+-'.join('-' * width for width in col_widths))
    for row in rows:
        print(fmt_line(row))


def report_recent_trends(db_path: str, days: int, end_date: str = None, diff_step: float = 1.0, drop_step: float = 5.0, table_name: str = None):
    """简洁的统一汇总入口：返回最近 N 天每个股票的趋势报告，并打印表格。"""
    report = analyze_recent_stock_trends(db_path, days, end_date=end_date, diff_step=diff_step, drop_step=drop_step, table_name=table_name)
    format_recent_trends_report(report)
    return report


def setup_matplotlib_chinese():
    """优先选择支持中文的字体，避免中文绘图乱码。

    这一步很关键，因为很多股票分析图表的标题、轴标签和表名都带中文。
    如果系统没有中文字体，图像中的中文可能会显示成方框，影响可读性。
    """
    if plt is None or font_manager is None:
        return

    candidate_fonts = [
        'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Noto Sans CJK SC',
        'WenQuanYi Zen Hei', 'Arial Unicode MS', 'SimHei', 'Source Han Sans SC', 'sans-serif'
    ]
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    for font_name in candidate_fonts:
        if font_name in available_fonts:
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False
            return


def plot_recent_trends(db_path: str, days: int, end_date: str = None, table_name: str = None, max_tables: int = 10, save_path: str = None):
    """绘制最近 N 天的收盘价走势图。默认展示前 max_tables 个股票表。

    适用于快速对比多个股票在同一时间窗口内的价格走势，尤其适合观察相对强弱。
    """
    if plt is None:
        raise RuntimeError('未安装 matplotlib，请先执行: pip install matplotlib')

    setup_matplotlib_chinese()
    start_date, end = get_recent_date_range(days, end_date)
    conn = sqlite3.connect(db_path)
    try:
        tables = [table_name] if table_name else get_table_names(db_path)
        selected = []
        for table in tables:
            if not table_has_date_column(db_path, table):
                continue
            if not table_has_close_column(db_path, table):
                continue
            selected.append(table)
            if len(selected) >= max_tables:
                break

        if not selected:
            print('未找到可用于绘图的 close 列表。')
            return []

        plt.figure(figsize=(12, 7))
        colors = plt.cm.tab10.colors
        for idx, table in enumerate(selected):
            # 每张表取出该时间段的收盘价序列，并使用不同颜色区分股票。
            rows = conn.execute(
                f'SELECT date, close FROM "{table}" WHERE date >= ? AND date <= ? ORDER BY date',
                (start_date, end),
            ).fetchall()
            if not rows:
                continue
            dates = [row[0] for row in rows]
            closes = [float(row[1]) for row in rows if row[1] is not None]
            if not closes:
                continue
            color = colors[idx % len(colors)]
            plt.plot(dates, closes, marker='o', linewidth=1.5, color=color, label=table)

            # 用散点标注每条线的最高值位置，方便快速定位峰值点。
            max_idx = max(range(len(closes)), key=lambda i: closes[i])
            plt.scatter([dates[max_idx]], [closes[max_idx]], color=color, s=30, zorder=5)
            plt.annotate(
                f'{closes[max_idx]:.2f}',
                (dates[max_idx], closes[max_idx]),
                textcoords='offset points',
                xytext=(5, 5),
                fontsize=8,
                color=color,
            )

        plt.title(f'最近 {days} 天收盘价走势 ({start_date} ~ {end})')
        plt.xlabel('日期')
        plt.ylabel('收盘价')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=30)
        plt.legend(loc='best')
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200)
            print(f'已保存图表到: {save_path}')
        else:
            plt.show()
        return selected
    finally:
        conn.close()


def plot_top_drop_stocks(db_path: str, days: int, end_date: str = None, top_n: int = 5, diff_step: float = 1.0, save_path: str = None):
    """按跌幅从大到小排序，绘制前 top_n 只股票的收盘价趋势图。

    这通常用于筛选“最近一段时间回撤最深”的股票，帮助快速发现弱势板块或个股。
    """
    if plt is None:
        raise RuntimeError('未安装 matplotlib，请先执行: pip install matplotlib')
    if top_n <= 0:
        raise ValueError('top_n 必须大于 0')

    setup_matplotlib_chinese()
    report = analyze_recent_stock_trends(db_path, days, end_date=end_date, diff_step=diff_step)
    ranked = sorted(report.get('items', []), key=lambda item: (item.get('current_drop_pct') or -999, item['table']), reverse=True)[:top_n]

    if not ranked:
        print('没有足够的数据绘制跌幅排行图。')
        return []

    start_date, end = get_recent_date_range(days, end_date)
    conn = sqlite3.connect(db_path)
    try:
        plt.figure(figsize=(12, 7))
        colors = plt.cm.tab10.colors
        for idx, item in enumerate(ranked):
            table = item['table']
            rows = conn.execute(
                f'SELECT date, close FROM "{table}" WHERE date >= ? AND date <= ? ORDER BY date',
                (start_date, end),
            ).fetchall()
            if not rows:
                continue
            dates = [row[0] for row in rows]
            closes = [float(row[1]) for row in rows if row[1] is not None]
            if not closes:
                continue
            label = f"{table} ({item.get('current_drop_pct')}%)"
            color = colors[idx % len(colors)]
            plt.plot(dates, closes, marker='o', linewidth=1.5, color=color, label=label)
            max_idx = max(range(len(closes)), key=lambda i: closes[i])
            plt.scatter([dates[max_idx]], [closes[max_idx]], color=color, s=30, zorder=5)
            plt.annotate(
                f'{closes[max_idx]:.2f}',
                (dates[max_idx], closes[max_idx]),
                textcoords='offset points',
                xytext=(5, 5),
                fontsize=8,
                color=color,
            )

        plt.title(f'最近 {days} 天跌幅前 {len(ranked)} 只股票走势 ({start_date} ~ {end})')
        plt.xlabel('日期')
        plt.ylabel('收盘价')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=30)
        plt.legend(loc='best')
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200)
            print(f'已保存图表到: {save_path}')
        else:
            plt.show()
        return [item['table'] for item in ranked]
    finally:
        conn.close()


# ------------------------------------------------------------
# 5. 报告输出和绘图：CSV 导出、趋势图、跌幅图
# ------------------------------------------------------------

def export_report_to_csv(report, output_path: str = None):
    """将趋势报告导出成 CSV 文件，便于后续在 Excel 或其他工具中二次分析。"""
    import csv

    items = report.get('items', [])
    if not output_path:
        output_path = f"stock_trend_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    fieldnames = [
        'table', 'period_start', 'period_end', 'days', 'max_high', 'current_close',
        'current_drop_pct', 'drop_range_start', 'drop_range_end', 'drop_range_days',
        'open_low_drop_dominant_range_start', 'open_low_drop_dominant_range_end', 'open_low_drop_dominant_count'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            drop_range = item.get('drop_range_most') or {}
            open_low_bucket = item.get('open_low_drop_dominant') or {}
            writer.writerow({
                'table': item.get('table'),
                'period_start': item.get('period_start'),
                'period_end': item.get('period_end'),
                'days': item.get('days'),
                'max_high': item.get('max_high'),
                'current_close': item.get('current_close'),
                'current_drop_pct': item.get('current_drop_pct'),
                'drop_range_start': drop_range.get('range_start'),
                'drop_range_end': drop_range.get('range_end'),
                'drop_range_days': drop_range.get('days'),
                'open_low_drop_dominant_range_start': open_low_bucket.get('range_start'),
                'open_low_drop_dominant_range_end': open_low_bucket.get('range_end'),
                'open_low_drop_dominant_count': open_low_bucket.get('count'),
            })

    print(f'已导出报告到 CSV: {output_path}')
    return output_path


# ------------------------------------------------------------
# 6. 命令行入口：接收参数并调用对应分析函数
# ------------------------------------------------------------

def main():
    """命令行入口：根据参数选择不同的数据分析或绘图任务。

    典型用法：
    - python stock_stats.py --summary
    - python stock_stats.py --report-days 30
    - python stock_stats.py --plot-days 20 --plot-table bj920000
    - python stock_stats.py --plot-top-days 30 --plot-top 5
    """
    parser = argparse.ArgumentParser(description='股票数据库统计工具')
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='SQLite 数据库路径，默认 stock.db')
    parser.add_argument('--date', help='统计指定日期（YYYY-MM-DD）在各表中的记录数')
    parser.add_argument('--days', type=int, help='统计从当前日期往前 N 天内的数据，格式：--days 7')
    parser.add_argument('--table', dest='stock_table', help='指定单个股票表名进行统计或绘图，例如：--table bj920000')
    parser.add_argument('--summary', action='store_true', help='输出数据库总体统计概览')
    parser.add_argument('--diff-step', type=float, default=1.0, help='高低价差分组的步长，默认 1.0')
    parser.add_argument('--diff-days', type=int, help='按最近 N 天统计 high-low 差值分组，格式：--diff-days 30')
    parser.add_argument('--drop-days', type=int, help='按最近 N 天统计当前价相对周期最高价的跌幅，格式：--drop-days 30')
    parser.add_argument('--analyze-days', type=int, help='综合分析最近 N 天：高低差分组、跌幅分布与最多区间，格式：--analyze-days 30')
    parser.add_argument('--report-days', type=int, help='输出最近 N 天的统一趋势报告（同 --analyze-days），格式：--report-days 30')
    parser.add_argument('--plot-days', type=int, help='按最近 N 天绘制收盘价走势图，格式：--plot-days 30')
    parser.add_argument('--plot-table', help='指定一只股票表名绘制走势图，例如：--plot-table bj920000')
    parser.add_argument('--plot-top-days', type=int, help='绘制最近 N 天的跌幅前列股票趋势图，格式：--plot-top-days 30')
    parser.add_argument('--plot-top', type=int, help='绘制跌幅排行时取前 N 只股票，格式：--plot-top 5')
    parser.add_argument('--export-csv', help='导出趋势报告到 CSV 文件，例如：--export-csv report.csv')
    parser.add_argument('--save-plot', help='将图表保存到 PNG 文件，例如：--save-plot recent_trends.png')
    parser.add_argument('--open-low-days', type=int, help='统计最近 N 天每个股票开盘价相对最低价的跌幅分组，格式：--open-low-days 30')
    parser.add_argument('--open-low-step', type=float, default=5.0, help='开盘价与最低价跌幅分组步长，单位：%%，默认 5.0')
    parser.add_argument('--plot-open-low-days', type=int, help='绘制最近 N 天开盘价-最低价跌幅分组柱状图，格式：--plot-open-low-days 30')
    parser.add_argument('--plot-open-low-table', help='指定单个股票表绘制开盘价-最低价跌幅分组图，例如：--plot-open-low-table bj920000')
    args = parser.parse_args()

    if args.date:
        count_rows_by_date(args.db, args.date)
        return

    if args.days is not None:
        count_rows_by_recent_days(args.db, args.days)
        return

    if args.diff_days is not None:
        group_high_low_diff(args.db, days=args.diff_days, step=args.diff_step, table_name=args.stock_table)
        return

    if args.drop_days is not None:
        get_drop_ratio_from_period_high(args.db, days=args.drop_days, table_name=args.stock_table)
        return

    if args.analyze_days is not None:
        analyze_recent_stock_trends(args.db, days=args.analyze_days, diff_step=args.diff_step, table_name=args.stock_table)
        return

    if args.report_days is not None:
        report = report_recent_trends(args.db, days=args.report_days, diff_step=args.diff_step, table_name=args.stock_table)
        if args.export_csv:
            export_report_to_csv(report, args.export_csv)
        return

    if args.open_low_days is not None:
        group_open_low_drop_distribution(args.db, days=args.open_low_days, step=args.open_low_step, table_name=args.stock_table)
        return

    if args.plot_days is not None:
        plot_recent_trends(args.db, days=args.plot_days, table_name=args.plot_table, save_path=args.save_plot)
        return

    if args.plot_open_low_days is not None:
        plot_open_low_drop_distribution(
            args.db,
            days=args.plot_open_low_days,
            step=args.open_low_step,
            table_name=args.plot_open_low_table,
            save_path=args.save_plot,
        )
        return

    if args.plot_top is not None or args.plot_top_days is not None:
        days = args.plot_top_days or args.plot_top
        top_n = args.plot_top or 5
        plot_top_drop_stocks(args.db, days=days, top_n=top_n, save_path=args.save_plot)
        return

    if args.summary:
        summarize_stock_db(args.db)
        return

    summarize_stock_db(args.db)


if __name__ == '__main__':
    main()
