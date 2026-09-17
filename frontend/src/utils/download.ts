/**
 * 文件下载。
 *
 * 附件下载链接由后端签发并做权限校验，前端不拼接猜测路径：
 * 只接受后端返回的 download_url，或明确传入的 /api 路径。
 */
export function triggerBrowserDownload(url: string, filename?: string): void {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.rel = 'noopener'
  if (filename) {
    anchor.download = filename
  }
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
}

/** 把二维数组导出为 CSV（前端小数据量导出；大数据量应走后端导出任务）。 */
export function exportCsv(filename: string, headers: string[], rows: (string | number | null)[][]): void {
  const escape = (value: string | number | null): string => {
    const text = value === null || value === undefined ? '' : String(value)
    // 防止 Excel 公式注入：以 = + - @ 开头的文本前置单引号
    const guarded = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
    return `"${guarded.replace(/"/g, '""')}"`
  }
  const lines = [headers.map(escape).join(','), ...rows.map((row) => row.map(escape).join(','))]
  const blob = new Blob([`\uFEFF${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
  const objectUrl = URL.createObjectURL(blob)
  triggerBrowserDownload(objectUrl, filename)
  URL.revokeObjectURL(objectUrl)
}