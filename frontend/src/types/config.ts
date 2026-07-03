export interface ModelProvider {
  provider: string
  displayName: string
  enabled: boolean
  default: boolean
  model: string
  maxInputTokens: number
  maxOutputTokens: number
  rpmLimit: number
}

export interface RuntimeEnv {
  env: string
  appName: string
  version: string
  defaultModel: string
  timezone: string
}
