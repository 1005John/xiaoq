import { media } from '@kit.MediaKit';
import { abilityAccessCtrl, Permissions, wantAgent } from '@kit.AbilityKit';
import { backgroundTaskManager } from '@kit.BackgroundTasksKit';
import { BusinessError } from '@kit.BasicServicesKit';
import fs from '@ohos.file.fs';

export class Recorder {
  private recorder?: media.AVRecorder
  private output?: fs.File
  private outputPath: string = ''
  private paused: boolean = false
  private backgroundContext?: Context
  private continuousTaskId?: number

  get isRecording(): boolean {
    return this.recorder !== undefined
  }

  get isPaused(): boolean {
    return this.paused
  }

  private async beginBackgroundRecording(context: Context): Promise<void> {
    const resumeAgent = await wantAgent.getWantAgent({
      wants: [{ bundleName: 'com.xiaoq.mobile', moduleName: 'entry', abilityName: 'EntryAbility' }],
      actionType: wantAgent.OperationType.START_ABILITY,
      requestCode: 901,
    })
    // The phone runtime implements the UIAbility string-array overload. Its
    // newer ContinuousTaskRequest overload is exposed by the SDK but rejected
    // by this device as an invalid native request object.
    const notification = await backgroundTaskManager.startBackgroundRunning(
      context,
      ['audioRecording'],
      resumeAgent,
    )
    this.backgroundContext = context
    this.continuousTaskId = notification.continuousTaskId
  }

  private errorMessage(error: Error): string {
    const businessError = error as BusinessError
    return `[${businessError.code}] ${businessError.message}`
  }

  private async endBackgroundRecording(): Promise<void> {
    const context = this.backgroundContext
    const taskId = this.continuousTaskId
    this.backgroundContext = undefined
    this.continuousTaskId = undefined
    if (!context) {
      return
    }
    try {
      if (taskId !== undefined) {
        await backgroundTaskManager.stopBackgroundRunning(context, taskId)
      } else {
        await backgroundTaskManager.stopBackgroundRunning(context)
      }
    } catch (_) {
      // The system may already have cleared the continuous task.
    }
  }

  async start(context: Context): Promise<void> {
    if (this.recorder) {
      throw new Error('会议录音已经开始')
    }
    const atManager = abilityAccessCtrl.createAtManager()
    await atManager.requestPermissionsFromUser(context, ['ohos.permission.MICROPHONE'] as Permissions[])
    try {
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
      // The system verifies audio-recording background tasks against an active recorder.
      await this.beginBackgroundRecording(context)
    } catch (error) {
      console.error(`[Recorder] start failed: ${this.errorMessage(error as Error)}`)
      const recorder = this.recorder
      if (recorder) {
        try {
          await recorder.release()
        } catch (_) {
          // The recorder may not have reached the prepared state.
        }
      }
      if (this.output) {
        fs.closeSync(this.output)
      }
      this.output = undefined
      this.recorder = undefined
      await this.endBackgroundRecording()
      throw new Error(error instanceof Error ? this.errorMessage(error) : '录音初始化失败')
    }
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
      await this.endBackgroundRecording()
    }
    return this.outputPath
  }
}

// Retain the active recorder while the page is in the background.
export const meetingRecorder: Recorder = new Recorder()
