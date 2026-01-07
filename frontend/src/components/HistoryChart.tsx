import { useQuery } from '@tanstack/react-query';
import { SpinLoading } from 'antd-mobile';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';
import { healthRecordsService } from '../services/healthRecords.service';
import { useMemo } from 'react';

interface HistoryChartProps {
    type: string;
    petId: string;
}

export function HistoryChart({ type, petId }: HistoryChartProps) {
    const { data, isLoading, error } = useQuery({
        queryKey: ['stats', type, petId],
        queryFn: () => healthRecordsService.getStats(type, petId, 30),
    });

    const chartData = useMemo(() => {
        if (!data?.data) return [];

        // Aggregation logic for counts (asthma, defecation, etc.)
        const isCountType = ['asthma', 'defecation', 'litter', 'eye_drops', 'tooth_brushing', 'ear_cleaning'].includes(type);

        if (isCountType) {
            const aggregated: Record<string, number> = {};
            data.data.forEach(item => {
                const date = item.date.split(' ')[0]; // YYYY-MM-DD
                aggregated[date] = (aggregated[date] || 0) + 1;
            });
            return Object.entries(aggregated).map(([date, value]) => ({
                date: new Date(date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
                fullDate: date,
                value
            })).sort((a, b) => a.fullDate.localeCompare(b.fullDate));
        }

        // Direct mapping for values (weight, feeding)
        return data.data.map(item => ({
            date: new Date(item.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }),
            shortDate: new Date(item.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
            fullDate: item.date,
            value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0
        }));
    }, [data, type]);

    const isLineChart = ['weight', 'feeding'].includes(type);
    const valueLabel = useMemo(() => {
        if (type === 'weight') return 'Вес (кг)';
        if (type === 'feeding') return 'Вес порции (г)';
        return 'Количество';
    }, [type]);

    if (isLoading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px' }}>
                <SpinLoading />
            </div>
        );
    }

    if (error || !data) {
        return (
            <p style={{ color: '#FF453A', textAlign: 'center', padding: '32px 0' }}>
                Ошибка загрузки данных для графика
            </p>
        );
    }

    if (chartData.length === 0) {
        return (
            <p style={{ color: 'var(--app-text-secondary)', textAlign: 'center', padding: '32px 0' }}>
                Недостаточно данных для построения графика
            </p>
        );
    }

    return (
        <div style={{
            width: '100%',
            height: '300px',
            padding: '16px 8px 16px 0',
            backgroundColor: 'var(--app-card-background)',
            borderRadius: '12px',
            marginTop: '16px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'
        }}>
            <ResponsiveContainer width="100%" height="100%">
                {isLineChart ? (
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="var(--adm-color-primary)" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="var(--adm-color-primary)" stopOpacity={0} />
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
                            itemStyle={{ color: 'var(--adm-color-primary)' }}
                        />
                        <Area
                            type="monotone"
                            dataKey="value"
                            name={valueLabel}
                            stroke="var(--adm-color-primary)"
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
                            cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                        />
                        <Bar
                            dataKey="value"
                            name={valueLabel}
                            fill="var(--adm-color-primary)"
                            radius={[4, 4, 0, 0]}
                            barSize={20}
                        />
                    </BarChart>
                )}
            </ResponsiveContainer>
        </div>
    );
}
