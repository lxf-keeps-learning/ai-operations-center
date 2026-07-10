/**
 * Markdown 渲染工具 — 将后端/LLM 返回的 Markdown 安全渲染为 HTML
 *
 * 功能：
 *   renderSafeMarkdown(text, options)
 *     1. 将 Markdown 转为 HTML（使用 marked 库，GFM 模式）
 *     2. 清除危险标签（script / iframe / form 等）
 *     3. 移除事件处理器（onclick 等）和危险 URL 协议
 *     4. 可选：剥离运营分析报告标题（用于报告预览时避免重复）
 *
 * 安全策略：
 *   - 禁止标签：script, style, iframe, object, embed, link, meta, base, form, input, button, textarea, select
 *   - 移除属性：on* 事件、style、srcset
 *   - URL 安全：只允许 http: / https: / mailto: / tel: 协议
 *   - 外部链接：target="_blank" 时自动添加 rel="noopener noreferrer"
 */

import { marked } from 'marked'

const BLOCKED_TAGS = 'script,style,iframe,object,embed,link,meta,base,form,input,button,textarea,select'
const URL_ATTRIBUTES = new Set(['href', 'src', 'xlink:href', 'formaction'])
const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])

interface MarkdownRenderOptions {
  stripOperationHeading?: boolean
}

export function renderSafeMarkdown(
  text: string,
  options: MarkdownRenderOptions = {},
): string {
  let source = text.replace(/\r\n/g, '\n')
  if (options.stripOperationHeading) {
    source = source.replace(/^##\s*运营分析(?:报告|结论)\s*\n+/u, '')
  }

  const html = marked.parse(source.replace(/</g, '&lt;'), {
    async: false,
    gfm: true,
  }) as string

  return sanitizeHtml(html)
}

function sanitizeHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.body.querySelectorAll(BLOCKED_TAGS).forEach((element) => element.remove())

  doc.body.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase()
      if (name.startsWith('on') || name === 'style' || name === 'srcset') {
        element.removeAttribute(attribute.name)
        continue
      }
      if (URL_ATTRIBUTES.has(name) && !isSafeUrl(attribute.value)) {
        element.removeAttribute(attribute.name)
      }
    }

    if (element instanceof HTMLAnchorElement && element.target === '_blank') {
      element.rel = 'noopener noreferrer'
    }
  })

  return doc.body.innerHTML
}

function isSafeUrl(value: string): boolean {
  const normalized = value.trim()
  if (!normalized || normalized.startsWith('#') || normalized.startsWith('/')) {
    return true
  }

  try {
    return SAFE_PROTOCOLS.has(new URL(normalized, window.location.origin).protocol)
  } catch {
    return false
  }
}
