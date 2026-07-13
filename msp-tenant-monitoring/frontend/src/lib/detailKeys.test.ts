import { describe, it, expect } from 'vitest'
import { detailKey, projectDetail } from './detailKeys'

describe('detailKey', () => {
  it('produces the expected triple', () => {
    expect(detailKey('t1', 'sites')).toEqual(['tenant-detail', 't1', 'sites'])
  })
})

describe('projectDetail', () => {
  it('not fired + selected → undefined (skeleton)', () => {
    expect(projectDetail({ fired: false, selected: true, data: undefined, error: undefined })).toBe(undefined)
  })

  it('not fired + not selected → null (Fetch Now)', () => {
    expect(projectDetail({ fired: false, selected: false, data: undefined, error: undefined })).toBe(null)
  })

  it('fired + error truthy → null even when data is present', () => {
    expect(projectDetail({ fired: true, selected: true, data: [1, 2, 3], error: new Error('oops') })).toBe(null)
  })

  it('fired + no error + data undefined → undefined (in-flight)', () => {
    expect(projectDetail({ fired: true, selected: true, data: undefined, error: undefined })).toBe(undefined)
  })

  it('fired + no error + data array → the same array', () => {
    const arr = [{ id: 'x' }]
    expect(projectDetail({ fired: true, selected: true, data: arr, error: undefined })).toBe(arr)
  })
})
