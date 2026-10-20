import { describe, expect, it } from 'vitest'
import { valueScale } from '../../src/utils/chartScale'

describe('valueScale', () => {
  it('шкала округляется и накрывает все замеры', () => {
    const scale = valueScale([4.2, 4.5])
    expect(scale.domain).toEqual([4.1, 4.6])
    expect(scale.ticks).toContain(4.2)
    expect(scale.ticks).toContain(4.5)
    expect(scale.decimals).toBe(1)
  })

  it('деления идут ровным шагом', () => {
    const scale = valueScale([4.2, 4.5])
    const steps = scale.ticks.slice(1).map((tick, i) => Number((tick - scale.ticks[i]).toFixed(6)))
    expect(new Set(steps).size).toBe(1)
  })

  it('один замер получает полосу вокруг себя, а не нулевую ось', () => {
    const scale = valueScale([5])
    expect(scale.ticks.some((tick) => tick < 5)).toBe(true)
    expect(scale.ticks.some((tick) => tick > 5)).toBe(true)
  })

  it('нулевые замеры не уходят в минус', () => {
    const scale = valueScale([0, 0])
    expect(scale.domain[0]).toBe(0)
  })

  it('отрицательные замеры держат ось ниже нуля', () => {
    const scale = valueScale([-2, -1])
    expect(scale.domain[0]).toBeLessThan(0)
  })
})
