// Stroke icon paths on a 24x24 grid (rendered by AppIcon with round caps and joins).
export const ICON_PATHS = {
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  plus: 'M12 5v14M5 12h14',
  'chevron-down': 'M6 9l6 6 6-6',
  'chevron-right': 'M9 6l6 6-6 6',
  'arrow-right': 'M5 12h14M13 6l6 6-6 6',
  alert: 'M12 4L3 19.5h18L12 4zM12 10v4.5M12 17.2v.1',
  info: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 11v5M12 7.8v.1',
  lock: 'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 017 0v3',
  shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3zM9 12l2.2 2.2L15 10.5',
  trash: 'M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6',
  external: 'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5',
  search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM16.5 16.5L21 21',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 20c0-3.5 3.6-6 8-6s8 2.5 8 6',
  filter: 'M4 6h16M7 12h10M10 18h4',
  logout: 'M10 5H5v14h5M15 8l4 4-4 4M19 12H9',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z',
} as const

export type IconName = keyof typeof ICON_PATHS
