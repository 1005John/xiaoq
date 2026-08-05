import { media } from '@kit.MediaKit';
import { abilityAccessCtrl, Permissions } from '@kit.AbilityKit';
import fs from '@ohos.file.fs';

export class Recorder {
  private recorder?: media.AVRecorder
  private output?: fs.File
  private outputPath: string = ''
  private paused: boolean = false

  async start(context: Context): Promise<void> {
    const atManager = abilityAccessCtrl.createAtManager()
    await atManager.requestPermissionsFromUser(context, ['ohos.permission.MICROPHONE'] as Permissions[])
    this.outputPath = `${context.cacheDir}/meeting_${Date.now()}.m4a`
    this.output = fs.openSync(this.outputPath, fs.OpenMode.READ_WRITE | fs.OpenMode.CREATE | fs.OpenMode.TRUNC)
    this.recorder = await media.createAVRecorder()
    const profile: media.AVRecorderProfile = {
      audioBitrate: 64000,
      audioChannels: 1,
      audioCodec: media.CodecMimeType.AUDIO_AAC,
      audioSampleRate: 44100,
      fileFormat: media.ContainerFormatType.CFT_MPEG_4A,
    }
    await this.recorder.prepare({
      audioSourceType: media.AudioSourceType.AUDIO_SOURCE_TYPE_MIC,
      profile: profile,
      url: `fd://${this.output.fd}`,
    })
    await this.recorder.start()
    this.paused = false
  }

  async pauseOrResume(): Promise<boolean> {
    if (!this.recorder) {
      throw new Error('录音尚未开始')
    }
    if (this.paused) {
      await this.recorder.resume()
      this.paused = false
    } else {
      await this.recorder.pause()
      this.paused = true
    }
    return this.paused
  }

  async stop(): Promise<string> {
    if (!this.recorder || !this.output) {
      throw new Error('录音尚未开始')
    }
    const recorder = this.recorder
    const output = this.output
    this.recorder = undefined
    this.output = undefined
    this.paused = false
    try {
      await recorder.stop()
      await recorder.release()
    } finally {
      fs.closeSync(output)
    }
    return this.outputPath
  }
}
