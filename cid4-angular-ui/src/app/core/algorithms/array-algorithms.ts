import {
  BinarySearchTraceResult,
  BinarySearchTraceStep,
  DeduplicationResult,
  SortTraceResult,
  SortTraceStep,
} from "./types"

export function buildMergeSortTrace(input: number[]): SortTraceResult {
  const values = [...input]
  const steps: SortTraceStep[] = []
  let comparisons = 0
  let writes = 0

  const sortRange = (start: number, end: number): number[] => {
    if (end - start <= 1) {
      return values.slice(start, end)
    }

    const middle = Math.floor((start + end) / 2)
    const left = sortRange(start, middle)
    const right = sortRange(middle, end)
    const merged: number[] = []
    let leftIndex = 0
    let rightIndex = 0

    while (leftIndex < left.length || rightIndex < right.length) {
      const leftValue = left[leftIndex]
      const rightValue = right[rightIndex]

      if (rightIndex >= right.length || (leftIndex < left.length && leftValue <= rightValue)) {
        comparisons += rightIndex < right.length ? 1 : 0
        merged.push(leftValue)
        leftIndex += 1
      } else {
        comparisons += 1
        merged.push(rightValue)
        rightIndex += 1
      }
    }

    for (const [offset, value] of merged.entries()) {
      values[start + offset] = value
      writes += 1
    }

    steps.push({
      label: "Merge run",
      detail: `Merged indices ${start}-${end - 1}.`,
      values: [...values],
      activeIndices: range(start, end),
    })

    return merged
  }

  sortRange(0, values.length)

  return {
    algorithm: "Merge sort",
    steps,
    sortedValues: values,
    comparisons,
    writes,
  }
}

export function buildQuickSortTrace(input: number[]): SortTraceResult {
  const values = [...input]
  const steps: SortTraceStep[] = []
  let comparisons = 0
  let writes = 0

  const swap = (left: number, right: number): void => {
    if (left === right) {
      return
    }

    ;[values[left], values[right]] = [values[right], values[left]]
    writes += 2
  }

  const partition = (low: number, high: number): number => {
    const pivot = values[high]
    let boundary = low

    for (let index = low; index < high; index += 1) {
      comparisons += 1

      if (values[index] <= pivot) {
        swap(boundary, index)
        boundary += 1
      }
    }

    swap(boundary, high)
    steps.push({
      label: "Partition",
      detail: `Partitioned around pivot ${pivot} at index ${boundary}.`,
      values: [...values],
      activeIndices: range(low, high + 1),
    })
    return boundary
  }

  const quickSort = (low: number, high: number): void => {
    if (low >= high) {
      return
    }

    const pivotIndex = partition(low, high)
    quickSort(low, pivotIndex - 1)
    quickSort(pivotIndex + 1, high)
  }

  quickSort(0, values.length - 1)

  return {
    algorithm: "Quick sort",
    steps,
    sortedValues: values,
    comparisons,
    writes,
  }
}

export function buildThresholdBinarySearchTrace(
  sortedValues: number[],
  threshold: number,
): BinarySearchTraceResult {
  let low = 0
  let high = sortedValues.length - 1
  let answer = -1
  const steps: BinarySearchTraceStep[] = []

  while (low <= high) {
    const middle = Math.floor((low + high) / 2)
    const value = sortedValues[middle]
    const qualifies = value <= threshold

    steps.push({
      label: "Probe midpoint",
      detail: qualifies
        ? `${value} <= ${threshold}, so move left to find the first qualifying entry.`
        : `${value} > ${threshold}, so move right.`,
      low,
      high,
      middle,
      values: [...sortedValues],
      activeIndices: [low, middle, high],
    })

    if (qualifies) {
      answer = middle
      high = middle - 1
    } else {
      low = middle + 1
    }
  }

  return {
    threshold,
    index: answer,
    value: answer >= 0 ? sortedValues[answer] : null,
    steps,
  }
}

export function deduplicateByKey<T>(
  items: T[],
  getKey: (item: T) => string,
): DeduplicationResult<T> {
  const uniqueItems: T[] = []
  const duplicates: T[] = []
  const duplicateKeys = new Set<string>()
  const seen = new Set<string>()

  for (const item of items) {
    const key = getKey(item)

    if (seen.has(key)) {
      duplicates.push(item)
      duplicateKeys.add(key)
      continue
    }

    seen.add(key)
    uniqueItems.push(item)
  }

  return {
    uniqueItems,
    duplicates,
    duplicateKeys: [...duplicateKeys],
  }
}

function range(start: number, end: number): number[] {
  return Array.from({ length: Math.max(0, end - start) }, (_, index) => start + index)
}
