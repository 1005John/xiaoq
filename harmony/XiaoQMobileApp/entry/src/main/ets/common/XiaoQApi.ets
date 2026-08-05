import { http } from '@kit.NetworkKit';

export interface MeetingItem {
  filename: string
  html_filename: string
  updated_at: string
}

export interface MeetingJob {
  job_id: string
  status: string
  filename: string
  result_file: string
  error: string
}

export interface MeetingResult {
  filename: string
  markdown: string
  tasks: string[]
}

interface MeetingListResponse {
  items: MeetingItem[]
}

interface MeetingJobResponse {
  job: MeetingJob
}

export interface GimbalState {
  mode: string
  pan: number
  tilt: number
}

export interface ChatResponse {
  ok: boolean
  status: string
  text: string
  reply: string
}

interface TodoItem {
  id: number
}

interface TodoResponse {
  todo: TodoItem
}

export class XiaoQApi {
  static host: string = '192.168.137.220'
  static token: string = ''

  static configure(host: string, token: string): void {
    XiaoQApi.host = host.trim().replace('http://', '').replace('https://', '').replace(/\/$/, '')
    XiaoQApi.token = token.trim()
  }

  static streamUrl(): string {
    return `${XiaoQApi.baseUrl()}/api/camera?token=${encodeURIComponent(XiaoQApi.token)}`
  }

  static meetingUrl(filename: string): string {
    return `${XiaoQApi.baseUrl()}/api/meetings/files/${encodeURIComponent(filename)}?token=${encodeURIComponent(XiaoQApi.token)}`
  }

  static baseUrl(): string {
    return `http://${XiaoQApi.host}:8788`
  }

  private static async request(path: string, method: http.RequestMethod, body: string): Promise<string> {
    if (XiaoQApi.token.length === 0) {
      throw new Error('请先在设置中填写设备令牌')
    }
    const client: http.HttpRequest = http.createHttp()
    try {
      const response: http.HttpResponse = await client.request(`${XiaoQApi.baseUrl()}${path}`, {
        method: method,
        header: { 'X-XiaoQ-Token': XiaoQApi.token, 'Content-Type': 'application/json' },
        extraData: body,
        connectTimeout: 10000,
        readTimeout: 180000,
      })
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error(`请求失败 (${response.responseCode})`)
      }
      return response.result as string
    } finally {
      client.destroy()
    }
  }

  static async status(): Promise<boolean> {
    return Boolean(JSON.parse(await XiaoQApi.request('/api/status', http.RequestMethod.GET, '')).xiaoq_online)
  }

  static async chat(text: string, speakOnDevice: boolean): Promise<ChatResponse> {
    const result = JSON.parse(await XiaoQApi.request(
      '/api/chat',
      http.RequestMethod.POST,
      JSON.stringify({ text: text, speak: speakOnDevice })
    )) as ChatResponse
    return result
  }

  static async gimbal(pan: number, tilt: number): Promise<void> {
    await XiaoQApi.request('/api/gimbal', http.RequestMethod.POST, JSON.stringify({ pan: pan, tilt: tilt }))
  }

  static async releaseGimbal(): Promise<void> {
    await XiaoQApi.request('/api/gimbal/release', http.RequestMethod.POST, '{}')
  }

  static async gimbalState(): Promise<GimbalState> {
    const result: GimbalState = JSON.parse(
      await XiaoQApi.request('/api/gimbal/state', http.RequestMethod.GET, '')
    ) as GimbalState
    return result
  }

  static async setGimbalMode(mode: string): Promise<GimbalState> {
    const result: GimbalState = JSON.parse(
      await XiaoQApi.request('/api/gimbal/mode', http.RequestMethod.POST, JSON.stringify({ mode: mode }))
    ) as GimbalState
    return result
  }

  static async meetings(): Promise<MeetingItem[]> {
    const result = JSON.parse(await XiaoQApi.request('/api/meetings', http.RequestMethod.GET, '')) as MeetingListResponse
    return result.items || []
  }

  static async meetingJob(id: string): Promise<MeetingJob> {
    const result = JSON.parse(await XiaoQApi.request(
      `/api/meetings/jobs/${encodeURIComponent(id)}`, http.RequestMethod.GET, ''
    )) as MeetingJobResponse
    return result.job
  }

  static async meetingResult(filename: string): Promise<MeetingResult> {
    const result = JSON.parse(await XiaoQApi.request(
      `/api/meetings/results/${encodeURIComponent(filename)}`, http.RequestMethod.GET, ''
    )) as MeetingResult
    return result
  }

  static async createTodo(text: string, reminderTime: string, reminderDate: string): Promise<number> {
    const result = JSON.parse(await XiaoQApi.request('/api/todos', http.RequestMethod.POST, JSON.stringify({
      text: text,
      reminder_time: reminderTime,
      reminder_date: reminderDate,
    }))) as TodoResponse
    const todoId = Number(result.todo?.id)
    if (!Number.isInteger(todoId) || todoId <= 0) {
      throw new Error('小Q未返回待办编号')
    }
    return todoId
  }

  static async updateTodo(todoId: number, text: string, reminderTime: string, reminderDate: string): Promise<void> {
    await XiaoQApi.request(`/api/todos/${todoId}`, http.RequestMethod.PUT, JSON.stringify({
      text: text,
      reminder_time: reminderTime,
      reminder_date: reminderDate,
    }))
  }
}
