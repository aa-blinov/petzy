import { useQuery } from '@tanstack/react-query';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState } from './EmptyState';
import { ChartNoAxesColumn } from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';
import { healthRecordsService } from '../services/healthRecords.service';
import { useEventTypes } from '../hooks/useEventTypes';
import { parseRecordDate } from '../utils/relativeTime';
import { useMemo, useState } from 'react';
import { CapsuleTabs } from 'antd-mobile';

interface HistoryChartProps {
    type: string;
    petId: string;
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

    const chartData = useMemo(() => {
        if (!data?.data) return [];

        // Both branches parse through parseRecordDate. Passing the
        // backend's strings to `new Date()` read them in two different
        // timezones: the date-only form used here is ISO, so it landed on
        // UTC midnight and every bar was labelled a day early west of
        // UTC, while the date+time form below isn't ISO and was read as
        // local. Same field, two meanings.
        if (!isValueChart) {
            const aggregated: Record<string, number> = {};
            data.data.forEach(item => {
                const date = item.date.split(' ')[0]; // YYYY-MM-DD
                aggregated[date] = (aggregated[date] || 0) + 1;
            });
            return Object.entries(aggregated).map(([date, value]) => {
                const parsed = parseRecordDate(date);
                return {
                    date: parsed
                        ? parsed.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                        : date,
                    fullDate: date,
                    value
                };
            }).sort((a, b) => a.fullDate.localeCompare(b.fullDate));
        }

        // Direct mapping for values (weight, feeding, or a custom value-chart type)
        return data.data.map(item => {
            const parsed = parseRecordDate(item.date);
            return {
                date: parsed
                    ? parsed.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                    : item.date,
                shortDate: parsed
                    ? parsed.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                    : item.date,
                fullDate: item.date,
                value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0
            };
        });
    }, [data, isValueChart]);

    const isLineChart = isValueChart;
    const valueLabel = chart?.kind === 'value' ? (chart.value_label || 'Значение') : 'Количество';

    const renderContent = () => {
        if (isLoading) {
            return <LoadingSpinner fullscreen={false} />;
        }

        if (error || !data) {
            return (
                <p style={{ color: 'var(--app-danger-color)', textAlign: 'center', padding: '32px 0' }}>
                    Ошибка загрузки данных для графика
                </p>
            );
        }

        if (chartData.length === 0) {
            return (
                <EmptyState
                    icon={ChartNoAxesColumn}
                    title="Нет данных за период"
                    description="Переключите вкладку или добавьте записи — график построится автоматически."
                    compact
                />
            );
        }

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
                                dataKey="shortDate"
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
                            />
                            <Tooltip
                                formatter={(value: any) => [value, valueLabel]}
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
                            />
                        </AreaChart>
                    ) : (
                        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--app-border-color)" />
                            <XAxis
                                dataKey="date"
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
                            />
                            <Tooltip
                                formatter={(value: any) => [value, valueLabel]}
                                contentStyle={{
                                    backgroundColor: 'var(--app-card-background)',
                                    border: '1px solid var(--app-border-color)',
                                    borderRadius: '8px',
                                    color: 'var(--app-text-color)'
                                }}
                                cursor={{ fill: 'var(--app-white-05)' }}
                            />
                            <Bar
                                dataKey="value"
                                name={valueLabel}
                                fill="var(--app-primary-color)"
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
