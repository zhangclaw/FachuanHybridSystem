/** 消息列表组件 */

import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useWorkbenchChat } from '../hooks/use-workbench-chat'
import { MessageBubble, StreamingBubble } from './MessageBubble'

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const { messages, streamingMessage, isStreaming } = useWorkbenchChat()
  const prevCountRef = useRef(0)

  const isEmpty = messages.length === 0 && !isStreaming

  // Scroll to bottom when messages first load or new messages arrive
  useEffect(() => {
    const el = scrollRef.current
    if (!el || isEmpty) return

    const prevCount = prevCountRef.current
    prevCountRef.current = messages.length

    // Always scroll on first load (prevCount was 0, now has messages)
    const isFirstLoad = prevCount === 0 && messages.length > 0

    if (isFirstLoad) {
      // Delay to let DOM fully layout the new content
      setTimeout(() => {
        el.scrollTop = el.scrollHeight
      }, 50)
    } else {
      // For new messages, only auto-scroll if user is near bottom
      const threshold = 120
      const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
      if (isAtBottom) {
        requestAnimationFrame(() => {
          el.scrollTop = el.scrollHeight
        })
      }
    }
  }, [messages, isEmpty])

  // Auto-scroll during streaming
  useEffect(() => {
    if (!streamingMessage) return
    const el = scrollRef.current
    if (!el) return
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight
    })
  }, [streamingMessage])

  return (
    <ScrollArea ref={scrollRef} className="flex-1 overflow-y-auto">
      {isEmpty ? (
        <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
          <div className="text-center space-y-2">
            <div className="text-4xl">💬</div>
            <p>开始对话吧</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isStreaming && streamingMessage && <StreamingBubble message={streamingMessage} />}
        </div>
      )}
    </ScrollArea>
  )
}
