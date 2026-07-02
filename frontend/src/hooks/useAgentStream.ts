import { onBeforeUnmount, ref } from 'vue'

import { createAgentStream, type AgentStreamController } from '@/api/runtime'
import type { StreamEventPayload, StreamStatus } from '@/types/api'

export function useAgentStream() {
  const status = ref<StreamStatus>('idle')
  const content = ref('')
  const events = ref<StreamEventPayload[]>([])
  const errorMessage = ref('')
  let controller: AgentStreamController | null = null

  function connect(traceId: string, sessionId?: string) {
    close('stopped')
    status.value = 'running'
    content.value = ''
    events.value = []
    errorMessage.value = ''

    controller = createAgentStream(
      { traceId, sessionId },
      {
        onEvent(event) {
          events.value.push(event)

          if (event.event === 'token' && typeof event.content === 'string') {
            status.value = 'streaming'
            content.value += event.content
          }

          if (event.event === 'done') {
            status.value = 'success'
            controller?.close()
            controller = null
          }

          if (event.event === 'stop') {
            status.value = 'stopped'
            controller?.close()
            controller = null
          }
        },
        onError(error) {
          status.value = 'failed'
          errorMessage.value = error.message
        },
      },
    )
  }

  function close(nextStatus: StreamStatus = 'stopped') {
    if (!controller) {
      return
    }

    controller.close()
    controller = null

    if (status.value === 'running' || status.value === 'streaming') {
      status.value = nextStatus
    }
  }

  onBeforeUnmount(() => close('stopped'))

  return {
    status,
    content,
    events,
    errorMessage,
    connect,
    close,
  }
}
