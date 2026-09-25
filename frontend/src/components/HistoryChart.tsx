import { useQuery } from '@tanstack/react-query';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState } from './EmptyState';
import { ChartNoAxesColumn } from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';
import type { ValueType } from 'recharts/types/component/DefaultTooltipContent';
import { healthRecordsService } from '../services/healthRecords.service';
import { useEventTypes } from '../hooks/useEventTypes';
import { parseRecordDate } from '../utils/relativeTime';
import { useMemo, useState } from 'react';
import { CapsuleTabs } from 'antd-mobile';

interface HistoryChartProps {
    type: string;
    petId: string;
}

type Granularity = 'day' | 'week' | 'month';

/**
 * Bucket size grows with the selected range so the chart stays readable
 * instead of rendering one bar/point per day even over "Всё время"
 * (3650 days) — hundreds of daily bars in a 300px-tall chart is just
 * visual noise, not more information.
 */
function granularityForDays(days: number): Granularity {
    if (days <= 60) return 'day';
    if (days <= 366) return 'week';
    return 'month';
}

const pad2 = (n: number) => String(n).padStart(2, '0');

/** Monday of the calendar week containing `d`, at local midnight. */
function startOfWeek(d: Date): Date {
    const start = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const weekday = start.getDay(); // 0 = Sunday .. 6 = Saturday
    const mondayOffset = weekday === 0 ? -6 : 1 - weekday;
    start.setDate(start.getDate() + mondayOffset);
    return start;
}

/**
 * Which bucket `date` falls into at the given granularity: a sortable
 * string key (built from local y/m/d — never `toISOString()`, which
 * converts to UTC and can shift the key to a different day/week/month
 * than the one the viewer sees) plus the bucket's own start date, used
 * for display formatting.
 */
function bucketFor(date: Date, granularity: Granularity): { key: string; start: Date } {
    if (granularity === 'month') {
        const start = new Date(date.getFullYear(), date.getMonth(), 1);
        return { key: `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`, start };
    }
    if (granularity === 'week') {
        const start = startOfWeek(date);
        return { key: `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-${pad2(start.getDate())}`, start };
    }
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    return { key: `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`, start };
}

/** Short label for the X axis tick — stays compact at any granularity. */
function formatBucketLabel(start: Date, granularity: Granularity): string {
    if (granularity === 'month') {
        return start.toLocaleDateString('ru-RU', { month: 'short', year: '2-digit' });
    }
    return start.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

/** Fuller label for the tooltip header — a week/month is a range, not a point. */
function formatBucketTooltipLabel(start: Date, granularity: Granularity): string {
    if (granularity === 'month') {
        return start.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    }
    if (granularity === 'week') {
        const end = new Date(start);
        end.setDate(end.getDate() + 6);
        const startLabel = start.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
        const endLabel = end.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
        return `${startLabel} – ${endLabel}`;
    }
    return start.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

interface ChartPoint {
    key: string;
    label: string;
    tooltipLabel: string;
    value: number;
}

export function HistoryChart({ type, petId }: HistoryChartProps) {
    const [days, setDays] = useState('30');
    const { eventTypesByKey } = useEventTypes();

    const { data, isLoading, error } = useQuery({
        queryKey: ['stats', type, petId, days],
        queryFn: () => healthRecordsService.getStats(type, petId, parseInt(days, 10)),
    });

    // Medications aren't in the registry (their own domain); every other
    // type's chart shape comes from `event_types.chart` — a custom type
    // gets a working chart with zero extra code.
    const chart = type === 'medications' ? { kind: 'count' as const } : eventTypesByKey[type]?.chart;
    const isValueChart = chart?.kind === 'value';
    const granularity = granularityForDays(parseInt(days, 10));

    const chartData = useMemo((): ChartPoint[] => {
        if (!data?.data) return [];

        // One bucket per (day|week|month) depending on the selected range.
        // Count charts sum occurrences per bucket (as before, just coarser
        // for long ranges); value charts (weight, feeding amount, …) now
        // average readings that land in the same bucket instead of
        // plotting one point per record — at day granularity that also
        // folds multiple same-day entries into one point, which reads
        // cleaner than several points stacked at the same X position.
        const buckets = new Map<string, { start: Date; sum: number; count: number }>();
        data.data.forEach(item => {
            const parsed = parseRecordDate(item.date);
            if (!parsed) return;
            const { key, start } = bucketFor(parsed, granularity);
            const value = isValueChart
                ? (typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0)
                : 1;
            const existing = buckets.get(key);
            if (existing) {
                existing.sum += value;
                existing.count += 1;
            } else {
                buckets.set(key, { start, sum: value, count: 1 });
            }
        });

        return Array.from(buckets.entries())
            .map(([key, { start, sum, count }]) => ({
                key,
                label: formatBucketLabel(start, granularity),
                tooltipLabel: formatBucketTooltipLabel(start, granularity),
                // Average for values (a sensible trend statistic — e.g. a
                // week's mean weight); a plain total for counts. Rounded
                // to one decimal so an averaged weight doesn't show up as
                // 28.733333333333334 in the tooltip.
                value: isValueChart ? Math.round((sum / count) * 10) / 10 : sum,
            }))
            .sort((a, b) => a.key.localeCompare(b.key));
    }, [data, isValueChart, granularity]);

    const isLineChart = isValueChart;
    const valueLabel = chart?.kind === 'value' ? (chart.value_label || 'Значение') : 'Количество';

    const renderContent = () => {
        if (isLoading) {
            return <LoadingSpinner fullscreen={false} />;
        }

        if (error || !data) {
            return (
                <p style={{ color: 'var(--app-danger-text)', textAlign: 'center', padding: '32px 0' }}>
                    Не удалось загрузить данные для графика
                </p>
            );
        }

        if (chartData.length === 0) {
            return (
                <EmptyState
                    icon={ChartNoAxesColumn}
                    title="Нет данных за период"
                    description="Переключите вкладку или добавьте записи, и график построится автоматически"
                    compact
                />
            );
        }

        // The tooltip header defaults to the X-axis field's raw value
        // (the short tick label) unless overridden — for a week/month
        // bucket that's too terse to read as a range, so look up the
        // fuller label from the hovered point's own data instead.
        const labelFormatter = (_label: string, payload: readonly { payload?: ChartPoint }[]) =>
            payload?.[0]?.payload?.tooltipLabel ?? _label;

        return (
            <div style={{
                width: '100%',
                minWidth: 0,
                height: '300px',
                minHeight: '300px',
                padding: '16px 8px 16px 0',
                backgroundColor: 'var(--app-card-background)',
                borderRadius: '12px',
                marginTop: '16px',
                boxShadow: 'var(--app-shadow-light)'
            }}>
                <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                    {isLineChart ? (
                        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--app-primary-color)" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="var(--app-primary-color)" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--app-border-color)" />
                            <XAxis
                                dataKey="label"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: 'var(--app-text-secondary)', fontSize: 10 }}
                                minTickGap={20}
                            />
                            <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: 'var(--app-text-secondary)', fontSize: 10 }}
                                width={35}
                                label={{
                                    value: valueLabel,
                                    angle: -90,
                                    position: 'insideLeft',
                                    style: { textAnchor: 'middle', fill: 'var(--app-text-secondary)', fontSize: 11 },
                                }}
                            />
                            <Tooltip
                                cursor={false}
                                labelFormatter={labelFormatter}
                                formatter={(value: ValueType | undefined) => [value, valueLabel]}
                                contentStyle={{
                                    backgroundColor: 'var(--app-card-background)',
                                    border: '1px solid var(--app-border-color)',
                                    borderRadius: '8px',
                                    color: 'var(--app-text-color)'
                                }}
                                itemStyle={{ color: 'var(--app-primary-color)' }}
                            />
                            <Area
                                type="monotone"
                                dataKey="value"
                                name={valueLabel}
                                stroke="var(--app-primary-color)"
                                fillOpacity={1}
                                fill="url(#colorValue)"
                                strokeWidth={2}
                                // Tapping a point drew a ringed dot on top of it in
                                // addition to the tooltip already saying which point
                                // it is — one highlight too many. The tooltip alone
                                // is enough.
                                activeDot={false}
                            />
                        </AreaChart>
                    ) : (
                        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--app-border-color)" />
                            <XAxis
                                dataKey="label"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: 'var(--app-text-secondary)', fontSize: 10 }}
                            />
                            <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: 'var(--app-text-secondary)', fontSize: 10 }}
                                allowDecimals={false}
                                width={35}
                                label={{
                                    value: valueLabel,
                                    angle: -90,
                                    position: 'insideLeft',
                                    style: { textAnchor: 'middle', fill: 'var(--app-text-secondary)', fontSize: 11 },
                                }}
                            />
                            <Tooltip
                                cursor={false}
                                labelFormatter={labelFormatter}
                                formatter={(value: ValueType | undefined) => [value, valueLabel]}
                                contentStyle={{
                                    backgroundColor: 'var(--app-card-background)',
                                    border: '1px solid var(--app-border-color)',
                                    borderRadius: '8px',
                                    color: 'var(--app-text-color)'
                                }}
                            />
                            <Bar
                                dataKey="value"
                                name={valueLabel}
                                fill="var(--app-primary-color)"
                                // Recharts outlines the tapped bar by default on top
                                // of the tooltip that already names it — one
                                // highlight too many. The tooltip alone is enough.
                                activeBar={false}
                                radius={[4, 4, 0, 0]}
                                barSize={20}
                            />
                        </BarChart>
                    )}
                </ResponsiveContainer>
            </div>
        );
    };

    return (
        <div style={{ marginTop: '16px' }}>
            <CapsuleTabs
                activeKey={days}
                onChange={v => setDays(v)}
            >
                <CapsuleTabs.Tab title="1 мес" key="30" />
                <CapsuleTabs.Tab title="3 мес" key="90" />
                <CapsuleTabs.Tab title="Полгода" key="180" />
                <CapsuleTabs.Tab title="Всё время" key="3650" />
            </CapsuleTabs>

            {renderContent()}
        </div>
    );
}
