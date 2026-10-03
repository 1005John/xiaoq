import { webview } from '@kit.ArkWeb';
import { promptAction } from '@kit.ArkUI';
import { preferences } from '@kit.ArkData';
import { XiaoQApi, RegisteredFace } from '../common/XiaoQApi';
import { meetingRecorder } from '../common/Recorder';
import { Uploader } from '../common/Uploader';

interface MeetingActionItem {
  text: string
  reminderDate: string
  reminderTime: string
  created: boolean
  todoId: number
}

@Entry
@Component
struct Index {
  @State tab: number = 0
  @State host: string = '192.168.137.116'
  @State token: string = ''
  @State online: string = '未连接'
  @State chatText: string = ''
  @State talkState: string = '输入文字后发送给小Q'
  @State chatReply: string = ''
  @State pttActive: boolean = false
  @State ttsVolume: number = 60
  @State speakOnDevice: boolean = false
  @State attachCamera: boolean = false
  @State pan: number = 90
  @State tilt: number = 150
  @State manualMode: boolean = false
  @State remoteState: string = '自动模式：表情控制云台'
  @State registeredFaces: RegisteredFace[] = []
  @State activeFaceId: string = ''
  @State newFaceName: string = ''
  @State faceState: string = '未指定跟随对象：检测到的人脸会正常跟随'
  @State runtimeState: string = '小Q状态未知'
  @State runtimeBusy: boolean = false
  // Keep the Web component absent until the paired token is available. This
  // makes saving settings construct a fresh, authenticated camera request.
  @State cameraUrl: string = ''
  @State showCamera: boolean = false
  @State photoUrl: string = ''
  @State showPhoto: boolean = false
  @State photoState: string = '等待小Q拍照'
  @State meetingState: string = '准备录制会议'
  @State meetingRecording: boolean = false
  @State meetingPaused: boolean = false
  @State meetingMarkdown: string = ''
  @State meetingFile: string = ''
  @State meetingActions: MeetingActionItem[] = []
  private cameraController: webview.WebviewController = new webview.WebviewController()
  private photoController: webview.WebviewController = new webview.WebviewController()
  private cameraRefreshId: number = 0
  private photoRefreshId: number = 0
  private photoPollTimer: number = -1
  private pttPressed: boolean = false

  aboutToAppear(): void {
    this.loadSavedConnection()
    this.refreshCameraStream()
    this.startPhotoPolling()
    this.refreshLatestPhoto()
    this.syncGimbalMode()
    this.syncFaces()
    this.syncMeetingRecorder()
  }

  aboutToDisappear(): void {
    if (this.photoPollTimer >= 0) {
      clearInterval(this.photoPollTimer)
      this.photoPollTimer = -1
    }
  }

  onPageShow(): void {
    this.refreshCameraStream()
    this.startPhotoPolling()
    this.refreshLatestPhoto()
    this.syncMeetingRecorder()
  }

  private syncMeetingRecorder(): void {
    this.meetingRecording = meetingRecorder.isRecording
    this.meetingPaused = meetingRecorder.isPaused
    if (this.meetingRecording) {
      this.meetingState = this.meetingPaused ? '已暂停录音' : '录音中（可锁屏或切到后台）'
    }
  }

  private startPhotoPolling(): void {
    if (this.photoPollTimer >= 0) {
      return
    }
    this.photoPollTimer = setInterval((): void => {
      if (this.tab === 1) {
        this.refreshLatestPhoto()
      }
    }, 3000)
  }

  private async refreshLatestPhoto(): Promise<void> {
    if (this.token.trim().length === 0) {
      return
    }
    this.applyConnection()
    try {
      const status = await XiaoQApi.photoStatus()
      if (!status.available) {
        this.photoState = '等待小Q拍照'
        return
      }
      const label = status.source === 'face_authorization_failure'
        ? '人脸授权失败抓拍'
        : (status.source === 'hailo_open_palm' ? '手势拍照' : '最新照片')
      this.photoState = `${label}：${status.captured_at}`
      const source = `${XiaoQApi.photoPageUrl()}&refresh=${encodeURIComponent(status.captured_at)}`
      if (source === this.photoUrl) {
        return
      }
      const refreshId = ++this.photoRefreshId
      this.showPhoto = false
      setTimeout((): void => {
        if (refreshId !== this.photoRefreshId) {
          return
        }
        this.photoUrl = source
        this.showPhoto = true
      }, 80)
    } catch (_) {
      this.photoState = '暂时无法获取拍照结果'
    }
  }

  private connectionStore(): preferences.Preferences {
    return preferences.getPreferencesSync(getContext(this), { name: 'xiaoq_connection' })
  }

  private loadSavedConnection(): void {
    try {
      const store = this.connectionStore()
      const savedHost = String(store.getSync('host', '192.168.137.116'))
      // Migrate the address used by older app builds when the saved value was
      // the previous Raspberry Pi lease.
      this.host = savedHost === '192.168.137.220' ? '192.168.137.116' : savedHost
      this.token = String(store.getSync('token', ''))
      this.speakOnDevice = Boolean(store.getSync('speak_on_device', false))
      this.attachCamera = Boolean(store.getSync('attach_camera', false))
    } catch (error) {
      this.message('无法读取已保存的连接配置')
    }
  }

  private async saveConnection(): Promise<void> {
    const store = this.connectionStore()
    store.putSync('host', this.host.trim())
    store.putSync('token', this.token.trim())
    store.putSync('speak_on_device', this.speakOnDevice)
    store.putSync('attach_camera', this.attachCamera)
    await store.flush()
  }

  private applyConnection(): void {
    XiaoQApi.configure(this.host, this.token)
  }

  private refreshCameraStream(): void {
    this.applyConnection()
    const source = this.token.trim().length > 0
      ? `${XiaoQApi.streamUrl()}&refresh=${Date.now()}` : ''
    const refreshId = ++this.cameraRefreshId
    // Recreate Web instead of relying on a stopped MJPEG connection to reload.
    this.showCamera = false
    setTimeout((): void => {
      if (refreshId !== this.cameraRefreshId) {
        return
      }
      this.cameraUrl = source
      this.showCamera = source.length > 0
    }, 80)
  }

  private message(text: string): void {
    promptAction.showToast({ message: text, duration: 2000 })
  }

  private async checkConnection(): Promise<void> {
    this.refreshCameraStream()
    try {
      await this.saveConnection()
      this.online = await XiaoQApi.status() ? '小Q在线' : '小Q未运行'
      await this.syncGimbalMode()
      await this.refreshRuntimeState()
    } catch (error) {
      this.online = `连接失败: ${(error as Error).message}`
    }
  }

  private async refreshRuntimeState(): Promise<void> {
    this.applyConnection()
    try {
      const state = await XiaoQApi.runtimeState()
      this.runtimeState = state.xiaoq_service === 'active' ? '小Q运行中' : '小Q已关闭'
    } catch (error) {
      this.runtimeState = '无法读取小Q状态'
    }
  }

  private async startXiaoQ(): Promise<void> {
    this.runtimeBusy = true
    this.applyConnection()
    try {
      const state = await XiaoQApi.startXiaoQ()
      this.runtimeState = state.xiaoq_service === 'active' ? '小Q运行中' : `小Q状态：${state.xiaoq_service}`
      this.online = '小Q在线'
      this.message('小Q已启动')
    } catch (error) {
      this.message((error as Error).message)
    } finally {
      this.runtimeBusy = false
    }
  }

  private async stopXiaoQ(): Promise<void> {
    this.runtimeBusy = true
    this.applyConnection()
    try {
      const state = await XiaoQApi.stopXiaoQ()
      this.runtimeState = state.xiaoq_service === 'inactive' ? '小Q已关闭' : `小Q状态：${state.xiaoq_service}`
      this.online = '小Q未运行'
      this.message('小Q已关闭')
    } catch (error) {
      this.message((error as Error).message)
    } finally {
      this.runtimeBusy = false
    }
  }

  private async poweroffPi(): Promise<void> {
    this.runtimeBusy = true
    this.applyConnection()
    try {
      await XiaoQApi.poweroffPi()
      this.runtimeState = '树莓派正在关机'
      this.online = '树莓派正在关机'
      this.message('树莓派正在关机')
    } catch (error) {
      this.message((error as Error).message)
    } finally {
      this.runtimeBusy = false
    }
  }

  private confirmPoweroff(): void {
    AlertDialog.show({
      title: '关闭树莓派',
      message: '树莓派将停止小Q和手机控制服务，需手动重新上电后才能连接。',
      primaryButton: {
        value: '取消',
        action: (): void => {}
      },
      secondaryButton: {
        value: '确认关机',
        action: (): void => { this.poweroffPi() }
      }
    })
  }

  private async sendText(): Promise<void> {
    if (this.chatText.trim().length === 0) {
      this.message('请输入要发送的内容')
      return
    }
    this.applyConnection()
    try {
      this.talkState = this.attachCamera ? '正在拍摄并请求视觉回答...' : '正在请求小Q回答...'
      const result = this.attachCamera
        ? await XiaoQApi.visionChat(this.chatText.trim(), this.speakOnDevice)
        : await XiaoQApi.chat(this.chatText.trim(), this.speakOnDevice)
      this.chatReply = result.reply || '小Q已收到消息，但树莓派服务没有返回文字回复，请更新树莓派端程序'
      if (this.attachCamera) {
        this.talkState = this.speakOnDevice
          ? '已用摄像头画面回答，并将在设备扬声器播报'
          : '已用摄像头画面回答'
      } else {
        this.talkState = this.speakOnDevice ? '小Q已回复，并将在设备扬声器播报' : '小Q已回复'
      }
      this.chatText = ''
    } catch (error) {
      this.talkState = this.attachCamera ? '视觉回答失败，请检查摄像头和网络' : '文字回答失败，请稍后重试'
      this.message((error as Error).message)
    }
  }

  private async startPtt(): Promise<void> {
    if (this.pttPressed) {
      return
    }
    this.pttPressed = true
    this.pttActive = true
    this.talkState = '正在通过小Q麦克风录音...'
    this.applyConnection()
    try {
      await XiaoQApi.pttStart(this.speakOnDevice, this.attachCamera)
    } catch (error) {
      this.pttPressed = false
      this.pttActive = false
      this.talkState = '无法启动小Q录音'
      this.message((error as Error).message)
    }
  }

  private async stopPtt(): Promise<void> {
    if (!this.pttPressed) {
      return
    }
    this.pttPressed = false
    this.pttActive = false
    this.talkState = '小Q正在识别语音并回复...'
    this.applyConnection()
    try {
      await XiaoQApi.pttStop()
    } catch (error) {
      this.talkState = '无法停止小Q录音'
      this.message((error as Error).message)
    }
  }

  private async togglePersona(): Promise<void> {
    this.applyConnection()
    try {
      await XiaoQApi.togglePersona()
      this.talkState = '已切换表情风格、人格和音色（与 F2 相同）'
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async setTtsVolume(value: number): Promise<void> {
    const percent = Math.max(0, Math.min(100, Math.round(value)))
    this.ttsVolume = percent
    this.applyConnection()
    try {
      await XiaoQApi.setTtsVolume(percent)
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async moveGimbal(): Promise<void> {
    if (!this.manualMode) {
      return
    }
    this.applyConnection()
    try {
      await XiaoQApi.gimbal(this.pan, this.tilt)
      this.remoteState = `手动模式：P${this.pan}° / T${this.tilt}°`
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async syncGimbalMode(): Promise<void> {
    this.applyConnection()
    try {
      const state = await XiaoQApi.gimbalState()
      this.manualMode = state.mode === 'manual'
      this.pan = state.pan
      this.tilt = state.tilt
      this.remoteState = this.manualMode
        ? `手动模式：P${this.pan}° / T${this.tilt}°`
        : '自动模式：表情控制云台'
    } catch (error) {
      this.remoteState = '无法获取云台模式'
    }
  }

  private async toggleGimbalMode(): Promise<void> {
    this.applyConnection()
    try {
      const state = await XiaoQApi.setGimbalMode(this.manualMode ? 'auto' : 'manual')
      this.manualMode = state.mode === 'manual'
      this.pan = state.pan
      this.tilt = state.tilt
      this.remoteState = this.manualMode
        ? `手动模式：P${this.pan}° / T${this.tilt}°`
        : '自动模式：表情控制云台'
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async syncFaces(): Promise<void> {
    if (this.token.trim().length === 0) {
      return
    }
    this.applyConnection()
    try {
      const result = await XiaoQApi.faces()
      this.registeredFaces = result.people || []
      this.activeFaceId = result.active_person_id || ''
      const active = this.registeredFaces.find((item: RegisteredFace): boolean => item.id === this.activeFaceId)
      this.faceState = active
        ? `只跟随：${active.name}；未找到时恢复表情联动`
        : '未指定跟随对象：检测到的人脸会正常跟随'
    } catch (_) {
      this.faceState = '暂时无法读取人脸列表'
    }
  }

  private async registerFace(): Promise<void> {
    const name = this.newFaceName.trim()
    if (name.length === 0) {
      this.message('请先输入姓名或称呼')
      return
    }
    this.applyConnection()
    try {
      await XiaoQApi.registerFace(name)
      this.newFaceName = ''
      this.faceState = `正在注册 ${name}，请按小Q语音提示面对摄像头`
      this.message('人脸注册已开始')
      setTimeout((): void => { this.syncFaces() }, 10000)
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async selectFace(personId: string): Promise<void> {
    this.applyConnection()
    try {
      await XiaoQApi.selectFace(personId)
      await this.syncFaces()
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async deleteFace(personId: string, name: string): Promise<void> {
    this.applyConnection()
    try {
      await XiaoQApi.deleteFace(personId)
      this.message(`已删除 ${name}`)
      await this.syncFaces()
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  build(): void {
    Column() {
      Row() {
        Text('小Q遥控').fontSize(24).fontWeight(FontWeight.Bold).fontColor('#F4F7FB')
        Blank()
        Text(this.online).fontSize(13).fontColor(this.online === '小Q在线' ? '#79DFA6' : '#F4C07A')
      }.width('100%').padding({ left: 20, right: 20, top: 16, bottom: 10 })
      Tabs({ barPosition: BarPosition.End }) {
        TabContent() { this.talkPage() }.tabBar(this.tabLabel('对讲', 0))
        TabContent() { this.remotePage() }.tabBar(this.tabLabel('遥控', 1))
        TabContent() { this.meetingPage() }.tabBar(this.tabLabel('会议', 2))
        TabContent() { this.settingsPage() }.tabBar(this.tabLabel('设置', 3))
      }.vertical(false).barHeight(54).width('100%').layoutWeight(1)
        .barBackgroundColor('#101722')
        .onChange((index: number): void => {
          this.tab = index
          if (index === 1) {
            this.refreshCameraStream()
            this.refreshLatestPhoto()
            this.syncGimbalMode()
            this.syncFaces()
          }
          if (index === 2) {
            this.syncMeetingRecorder()
            this.loadLatestMeeting()
          }
          if (index === 3) {
            this.refreshRuntimeState()
          }
        })
    }.width('100%').height('100%').backgroundColor('#101722')
  }

  @Builder
  private tabLabel(title: string, index: number): void {
    Text(title)
      .width('100%').height('100%').textAlign(TextAlign.Center)
      .fontSize(16).fontWeight(this.tab === index ? FontWeight.Medium : FontWeight.Regular)
      .fontColor(this.tab === index ? '#2E85FF' : '#AAB8CE')
  }

  @Builder
  private talkPage(): void {
    Column({ space: 18 }) {
      Text(this.talkState).fontColor('#C8D2E3').fontSize(15).width('100%')
      TextArea({ text: this.chatText, placeholder: '输入文字发给小Q' })
        .height(120).fontSize(17).backgroundColor('#1B2635').fontColor('#F4F7FB')
        .placeholderColor('#8290A4').onChange((value: string): void => { this.chatText = value })
      Button('发送文字').width('100%').onClick((): void => { this.sendText() })
      Button(this.pttActive ? '松开后发送语音' : '按住说话')
        .width('100%').height(56).fontSize(18)
        .backgroundColor(this.pttActive ? '#D8555F' : '#2E85FF')
        .onTouch((event: TouchEvent): void => {
          if (event.type === TouchType.Down) {
            this.startPtt()
          } else if (event.type === TouchType.Up || event.type === TouchType.Cancel) {
            this.stopPtt()
          }
        })
      Button('切换表情风格（F2）').width('100%').onClick((): void => { this.togglePersona() })
      Text(`TTS 播报音量 ${this.ttsVolume}%`).fontSize(14).fontColor('#C8D2E3').width('100%')
      Slider({ value: this.ttsVolume, min: 0, max: 100, step: 5 })
        .onChange((value: number): void => { this.setTtsVolume(value) })
      Row() {
        Toggle({ type: ToggleType.Switch, isOn: this.speakOnDevice })
          .onChange((isOn: boolean): void => {
            this.speakOnDevice = isOn
            this.saveConnection()
          })
        Text('同时让小Q扬声器播报').fontSize(14).fontColor('#C8D2E3').margin({ left: 10 })
      }.width('100%')
      Row() {
        Toggle({ type: ToggleType.Switch, isOn: this.attachCamera })
          .onChange((isOn: boolean): void => {
            this.attachCamera = isOn
            this.saveConnection()
          })
        Text('附带摄像头画面，用 MiMo 视觉回答').fontSize(14).fontColor('#C8D2E3').margin({ left: 10 })
      }.width('100%')
      if (this.chatReply.length > 0) {
        Column({ space: 8 }) {
          Text('小Q回复').fontSize(14).fontColor('#8290A4')
          Text(this.chatReply).fontSize(17).fontColor('#F4F7FB').width('100%')
        }.width('100%').padding(14).backgroundColor('#1B2635')
      }
    }.padding(20).alignItems(HorizontalAlign.Start).width('100%')
  }

  @Builder
  private remotePage(): void {
    Scroll() {
      Column({ space: 14 }) {
        if (this.showCamera && this.cameraUrl.length > 0) {
          Web({ src: this.cameraUrl, controller: this.cameraController })
            .width('100%').height(250).backgroundColor('#000000')
        } else {
          Text('请先在设置页保存设备令牌，再打开摄像头画面。')
            .width('100%').height(250).textAlign(TextAlign.Center)
            .fontSize(15).fontColor('#8290A4').backgroundColor('#000000')
        }
        Button('刷新画面').width('100%').onClick((): void => { this.refreshCameraStream() })
        Text(this.remoteState).fontSize(14).fontColor('#C8D2E3')
        Text(`左右 ${this.pan}°`).fontSize(16).fontColor('#F4F7FB')
        Slider({ value: this.pan, min: 75, max: 105, step: 1 })
          .enabled(this.manualMode)
          .onChange((value: number): void => { this.pan = Math.round(value); this.moveGimbal() })
        Text(`上下 ${this.tilt}°`).fontSize(16).fontColor('#F4F7FB')
        Slider({ value: this.tilt, min: 138, max: 162, step: 1 })
          .enabled(this.manualMode)
          .onChange((value: number): void => { this.tilt = Math.round(value); this.moveGimbal() })
        Button(this.manualMode ? '切换到自动' : '切换到手动')
          .width('100%').onClick((): void => { this.toggleGimbalMode() })
        Text(this.manualMode ? '手动模式下可通过滑杆控制云台。' : '自动模式下由小Q表情控制云台。')
          .fontSize(13).fontColor('#8290A4')
        Divider().color('#2A3648').strokeWidth(1)
        Text('人脸跟随').fontSize(18).fontColor('#F4F7FB').fontWeight(FontWeight.Medium)
        Text(this.faceState).fontSize(13).fontColor('#C8D2E3')
        Row({ space: 8 }) {
          TextInput({ text: this.newFaceName, placeholder: '输入姓名后注册' })
            .layoutWeight(1).backgroundColor('#1B2635').fontColor('#F4F7FB')
            .onChange((value: string): void => { this.newFaceName = value })
          Button('注册').onClick((): void => { this.registerFace() })
        }.width('100%')
        Button('跟随任意人脸').width('100%').onClick((): void => { this.selectFace('') })
        ForEach(this.registeredFaces, (item: RegisteredFace): void => {
          Row({ space: 8 }) {
            Column({ space: 2 }) {
              Text(item.name).fontSize(16).fontColor('#F4F7FB')
              Text(`${item.sample_count} 个特征样本`).fontSize(12).fontColor('#8290A4')
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Button(item.id === this.activeFaceId ? '正在跟随' : '跟随')
              .fontSize(13).onClick((): void => { this.selectFace(item.id) })
            Button('删除').fontSize(13).backgroundColor('#A85A36')
              .onClick((): void => { this.deleteFace(item.id, item.name) })
          }.width('100%').padding(10).backgroundColor('#162130')
        }, (item: RegisteredFace): string => item.id)
        Text(this.photoState).fontSize(14).fontColor('#C8D2E3')
        if (this.showPhoto && this.photoUrl.length > 0) {
          Text('小Q最新抓拍').fontSize(14).fontColor('#8290A4')
          Web({ src: this.photoUrl, controller: this.photoController })
            .width('100%').height(250).backgroundColor('#000000')
        }
      }.padding(20).alignItems(HorizontalAlign.Start).width('100%')
    }.width('100%').height('100%')
  }

  private async startMeeting(): Promise<void> {
    this.applyConnection()
    try {
      await meetingRecorder.start(getContext(this))
      this.meetingRecording = true
      this.meetingPaused = false
      this.meetingState = '录音中'
      this.meetingMarkdown = ''
      this.meetingActions = []
    } catch (error) {
      this.message(`无法开始录音: ${(error as Error).message}`)
    }
  }

  private async pauseMeeting(): Promise<void> {
    try {
      this.meetingPaused = await meetingRecorder.pauseOrResume()
      this.meetingState = this.meetingPaused ? '已暂停录音' : '录音中'
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  private async stopMeeting(): Promise<void> {
    try {
      this.meetingState = '正在保存录音'
      const path = await meetingRecorder.stop()
      this.meetingRecording = false
      this.meetingPaused = false
      this.meetingState = '正在发送录音给小Q'
      this.applyConnection()
      const jobId = await Uploader.audio(getContext(this), path, true)
      this.meetingState = '小Q正在转写并生成会议纪要'
      this.pollMeeting(jobId, 0)
    } catch (error) {
      this.meetingRecording = false
      this.meetingPaused = false
      this.meetingState = '会议录音处理失败'
      this.message((error as Error).message)
    }
  }

  private async pollMeeting(jobId: string, attempts: number): Promise<void> {
    try {
      const job = await XiaoQApi.meetingJob(jobId)
      if (job.status === 'completed' && job.result_file.length > 0) {
        await this.loadMeetingResult(job.result_file)
        this.meetingState = '会议纪要已生成'
        return
      }
      if (job.status === 'failed') {
        this.meetingState = '会议纪要生成失败'
        this.message(job.error || '请稍后重试')
        return
      }
      if (attempts >= 90) {
        this.meetingState = '仍在处理，可点击会议纪要刷新结果'
        return
      }
      setTimeout((): void => { this.pollMeeting(jobId, attempts + 1) }, 4000)
    } catch (error) {
      this.meetingState = '无法获取会议处理状态'
      this.message((error as Error).message)
    }
  }

  private async loadLatestMeeting(): Promise<void> {
    this.applyConnection()
    try {
      const meetings = await XiaoQApi.meetings()
      if (meetings.length > 0) {
        await this.loadMeetingResult(meetings[0].filename)
      }
    } catch (error) {
      // The meeting page remains usable before the first successful upload.
    }
  }

  private async loadMeetingResult(filename: string): Promise<void> {
    const result = await XiaoQApi.meetingResult(filename)
    this.meetingFile = result.filename
    this.meetingMarkdown = result.markdown
    this.meetingActions = result.tasks.map((text: string): MeetingActionItem => ({
      text: text,
      reminderDate: this.todayDate(),
      reminderTime: '09:00',
      created: false,
      todoId: 0,
    }))
  }

  private twoDigits(value: number): string {
    return value < 10 ? `0${value}` : `${value}`
  }

  private todayDate(): string {
    const today = new Date()
    return `${today.getFullYear()}-${this.twoDigits(today.getMonth() + 1)}-${this.twoDigits(today.getDate())}`
  }

  private dateFromText(value: string): Date {
    const parts = value.split('-').map((part: string): number => Number(part))
    if (parts.length === 3 && Number.isInteger(parts[0]) && Number.isInteger(parts[1]) && Number.isInteger(parts[2])) {
      return new Date(parts[0], parts[1] - 1, parts[2])
    }
    return new Date()
  }

  private updateMeetingActionText(index: number, text: string): void {
    const current = this.meetingActions[index]
    if (!current) {
      return
    }
    const actions = [...this.meetingActions]
    actions[index] = {
      text: text,
      reminderDate: current.reminderDate,
      reminderTime: current.reminderTime,
      created: current.created,
      todoId: current.todoId,
    }
    this.meetingActions = actions
  }

  private updateMeetingReminderDate(index: number, reminderDate: string): void {
    const current = this.meetingActions[index]
    if (!current) {
      return
    }
    const actions = [...this.meetingActions]
    actions[index] = {
      text: current.text,
      reminderDate: reminderDate,
      reminderTime: current.reminderTime,
      created: current.created,
      todoId: current.todoId,
    }
    this.meetingActions = actions
  }

  private updateMeetingReminderTime(index: number, reminderTime: string): void {
    const current = this.meetingActions[index]
    if (!current) {
      return
    }
    const actions = [...this.meetingActions]
    actions[index] = {
      text: current.text,
      reminderDate: current.reminderDate,
      reminderTime: reminderTime,
      created: current.created,
      todoId: current.todoId,
    }
    this.meetingActions = actions
  }

  private chooseMeetingReminderDate(index: number): void {
    const selected = this.dateFromText(this.meetingActions[index]?.reminderDate || this.todayDate())
    DatePickerDialog.show({
      start: new Date(2026, 0, 1),
      selected: selected,
      onDateAccept: (value: Date): void => {
        this.updateMeetingReminderDate(index,
          `${value.getFullYear()}-${this.twoDigits(value.getMonth() + 1)}-${this.twoDigits(value.getDate())}`)
      },
      onDateChange: (value: Date): void => {
        this.updateMeetingReminderDate(index,
          `${value.getFullYear()}-${this.twoDigits(value.getMonth() + 1)}-${this.twoDigits(value.getDate())}`)
      },
    })
  }

  private timeFromText(value: string): Date {
    const parts = value.split(':').map((part: string): number => Number(part))
    const selected = new Date()
    if (parts.length === 2 && Number.isInteger(parts[0]) && Number.isInteger(parts[1])
      && parts[0] >= 0 && parts[0] < 24 && parts[1] >= 0 && parts[1] < 60) {
      selected.setHours(parts[0], parts[1], 0, 0)
    } else {
      selected.setHours(9, 0, 0, 0)
    }
    return selected
  }

  private chooseMeetingReminderTime(index: number): void {
    const selected = this.timeFromText(this.meetingActions[index]?.reminderTime || '09:00')
    TimePickerDialog.show({
      selected: selected,
      useMilitaryTime: true,
      onAccept: (value: TimePickerResult): void => {
        this.updateMeetingReminderTime(index, `${this.twoDigits(value.hour)}:${this.twoDigits(value.minute)}`)
      },
      onChange: (value: TimePickerResult): void => {
        this.updateMeetingReminderTime(index, `${this.twoDigits(value.hour)}:${this.twoDigits(value.minute)}`)
      },
      onEnterSelectedArea: (value: TimePickerResult): void => {
        this.updateMeetingReminderTime(index, `${this.twoDigits(value.hour)}:${this.twoDigits(value.minute)}`)
      },
    })
  }

  private async createMeetingTodo(index: number): Promise<void> {
    const item = this.meetingActions[index]
    if (!item || item.text.trim().length < 2) {
      this.message('待办内容至少需要两个字符')
      return
    }
    try {
      this.applyConnection()
      const reminderTime = item.reminderTime.trim() || '09:00'
      const reminderDate = item.reminderDate.trim() || this.todayDate()
      const updating = item.todoId > 0
      if (updating) {
        await XiaoQApi.updateTodo(item.todoId, item.text.trim(), reminderTime, reminderDate)
      } else {
        item.todoId = await XiaoQApi.createTodo(item.text.trim(), reminderTime, reminderDate)
      }
      item.created = true
      this.meetingActions = [...this.meetingActions]
      this.message(updating ? '已更新小Q待办' : '已创建小Q待办')
    } catch (error) {
      this.message((error as Error).message)
    }
  }

  @Builder
  private meetingPage(): void {
    Scroll() {
      Column({ space: 14 }) {
        Text(this.meetingState).fontSize(16).fontColor('#C8D2E3').width('100%')
        if (!this.meetingRecording) {
          Button('启动录音').width('100%').onClick((): void => { this.startMeeting() })
        } else {
          Button(this.meetingPaused ? '继续录音' : '暂停录音')
            .width('100%').onClick((): void => { this.pauseMeeting() })
          Button('停止并生成会议纪要').width('100%').onClick((): void => { this.stopMeeting() })
        }
        Button('会议纪要').width('100%').onClick((): void => { this.loadLatestMeeting() })
        if (this.meetingMarkdown.length > 0) {
          Text(this.meetingFile).fontSize(13).fontColor('#8290A4').width('100%')
          Text(this.meetingMarkdown).fontSize(14).fontColor('#F4F7FB').width('100%')
            .backgroundColor('#1B2635').padding(12)
        }
        if (this.meetingActions.length > 0) {
          Text('待办事项').fontSize(19).fontColor('#F4F7FB').fontWeight(FontWeight.Medium).width('100%')
          ForEach(this.meetingActions, (item: MeetingActionItem, index: number) => {
            Column({ space: 8 }) {
              TextInput({ text: item.text, placeholder: '待办内容' })
                .fontSize(16).backgroundColor('#1B2635').fontColor('#F4F7FB')
                .onChange((value: string): void => {
                  this.updateMeetingActionText(index, value)
                })
              Row({ space: 8 }) {
                Button(item.reminderDate)
                  .width('49%').fontSize(14)
                  .onClick((): void => { this.chooseMeetingReminderDate(index) })
                Button(item.reminderTime)
                  .layoutWeight(1).fontSize(15)
                  .onClick((): void => { this.chooseMeetingReminderTime(index) })
              }.width('100%')
              Button(item.created ? '更新待办' : '创建待办')
                .width('100%').onClick((): void => { this.createMeetingTodo(index) })
            }.width('100%').padding(12).backgroundColor('#162130')
          // Include displayed fields in the key. ArkUI otherwise preserves the
          // cached list row after a picker callback replaces this item.
          }, (item: MeetingActionItem, index: number): string =>
            `${index}_${item.text}_${item.reminderDate}_${item.reminderTime}_${item.created}`)
        }
      }.padding(20).alignItems(HorizontalAlign.Start).width('100%')
    }.width('100%').height('100%')
  }

  @Builder
  private settingsPage(): void {
    Column({ space: 16 }) {
      Text('连接小Q').fontSize(20).fontColor('#F4F7FB').fontWeight(FontWeight.Medium)
      TextInput({ text: this.host, placeholder: '树莓派 IP 地址' })
        .onChange((value: string): void => { this.host = value })
        .backgroundColor('#1B2635').fontColor('#F4F7FB')
      TextInput({ text: this.token, placeholder: '设备令牌' })
        .onChange((value: string): void => { this.token = value })
        .backgroundColor('#1B2635').fontColor('#F4F7FB')
      Button('保存并测试连接').width('100%').onClick((): void => { this.checkConnection() })
      Text('设备令牌保存在树莓派 data/mobile_control_token。').fontSize(13).fontColor('#8290A4')
      Divider().color('#2A3648').strokeWidth(1)
      Text('设备控制').fontSize(20).fontColor('#F4F7FB').fontWeight(FontWeight.Medium)
      Text(this.runtimeState).fontSize(14).fontColor('#C8D2E3').width('100%')
      Row({ space: 10 }) {
        Button('启动小Q').layoutWeight(1).enabled(!this.runtimeBusy)
          .onClick((): void => { this.startXiaoQ() })
        Button('关闭小Q').layoutWeight(1).enabled(!this.runtimeBusy)
          .backgroundColor('#A85A36').onClick((): void => { this.stopXiaoQ() })
      }.width('100%')
      Button('树莓派关机').width('100%').enabled(!this.runtimeBusy)
        .backgroundColor('#B6404C').onClick((): void => { this.confirmPoweroff() })
    }.padding(20).alignItems(HorizontalAlign.Start).width('100%')
  }
}
