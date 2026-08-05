import { http } from '@kit.NetworkKit';
import fs from '@ohos.file.fs';
import util from '@ohos.util';
import { XiaoQApi } from './XiaoQApi';

interface UploadJobResponse {
  job_id: string
}

export class Uploader {
  static async audio(_context: Context, path: string, meeting: boolean): Promise<string> {
    if (XiaoQApi.token.length === 0) {
      throw new Error('请先在设置中填写设备令牌')
    }
    const file = fs.openSync(path, fs.OpenMode.READ_ONLY)
    let payload: ArrayBuffer
    try {
      const size = Number(fs.statSync(path).size)
      const source = new ArrayBuffer(size)
      fs.readSync(file.fd, source)
      const boundary = `----XiaoQ${Date.now()}`
      const name = path.substring(path.lastIndexOf('/') + 1)
      const encoder = new util.TextEncoder('utf-8')
      const prefix = encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${name}"\r\nContent-Type: audio/mp4\r\n\r\n`)
      const suffix = encoder.encode(`\r\n--${boundary}--\r\n`)
      const combined = new Uint8Array(prefix.length + source.byteLength + suffix.length)
      combined.set(prefix, 0)
      combined.set(new Uint8Array(source), prefix.length)
      combined.set(suffix, prefix.length + source.byteLength)
      payload = combined.buffer as ArrayBuffer
      const client = http.createHttp()
      try {
        const response = await client.request(
          `${XiaoQApi.baseUrl()}${meeting ? '/api/meetings' : '/api/voice'}`,
          {
            method: http.RequestMethod.POST,
            header: {
              'X-XiaoQ-Token': XiaoQApi.token,
              'Content-Type': `multipart/form-data; boundary=${boundary}`,
            },
            extraData: payload,
            connectTimeout: 15000,
            readTimeout: 60000,
          }
        )
        if (response.responseCode < 200 || response.responseCode >= 300) {
          throw new Error(`上传失败 (${response.responseCode})`)
        }
        return String((JSON.parse(response.result as string) as UploadJobResponse).job_id)
      } finally {
        client.destroy()
      }
    } finally {
      fs.closeSync(file)
    }
  }
}
