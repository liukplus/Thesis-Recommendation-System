import { useState, useEffect } from 'react'
import Button from '../components/UI/Button'
import './SettingsPage.css'

interface Settings {
  apiBaseUrl: string
  llmProvider: string
  llmModel: string
  apiKey: string
  maxSteps: number
  theme: string
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({
    apiBaseUrl: '/api/v1',
    llmProvider: 'deepseek',
    llmModel: 'deepseek-chat',
    apiKey: '',
    maxSteps: 5,
    theme: 'light',
  })

  const [saved, setSaved] = useState(false)

  useEffect(() => {
    // Load from localStorage
    const savedSettings = localStorage.getItem('app_settings')
    if (savedSettings) {
      try {
        setSettings(JSON.parse(savedSettings))
      } catch {
        // ignore
      }
    }
  }, [])

  const handleChange = (key: keyof Settings, value: string | number) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = () => {
    localStorage.setItem('app_settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    const defaults: Settings = {
      apiBaseUrl: '/api/v1',
      llmProvider: 'deepseek',
      llmModel: 'deepseek-chat',
      apiKey: '',
      maxSteps: 5,
      theme: 'light',
    }
    setSettings(defaults)
    localStorage.removeItem('app_settings')
  }

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <p className="settings-description">
        Configure the application settings. These are stored locally in your browser.
      </p>

      <div className="settings-section">
        <h2>API Configuration</h2>
        <div className="setting-item">
          <label htmlFor="apiBaseUrl">API Base URL</label>
          <input
            id="apiBaseUrl"
            type="text"
            value={settings.apiBaseUrl}
            onChange={(e) => handleChange('apiBaseUrl', e.target.value)}
          />
        </div>
      </div>

      <div className="settings-section">
        <h2>LLM Configuration</h2>
        <div className="setting-item">
          <label htmlFor="llmProvider">Provider</label>
          <select
            id="llmProvider"
            value={settings.llmProvider}
            onChange={(e) => handleChange('llmProvider', e.target.value)}
          >
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="zhipu">Zhipu AI (GLM)</option>
            <option value="tongyi">Tongyi Qianwen</option>
          </select>
        </div>
        <div className="setting-item">
          <label htmlFor="llmModel">Model</label>
          <input
            id="llmModel"
            type="text"
            value={settings.llmModel}
            onChange={(e) => handleChange('llmModel', e.target.value)}
          />
        </div>
        <div className="setting-item">
          <label htmlFor="apiKey">API Key</label>
          <input
            id="apiKey"
            type="password"
            value={settings.apiKey}
            onChange={(e) => handleChange('apiKey', e.target.value)}
            placeholder="Enter your API key..."
          />
          <p className="setting-hint">
            Your API key is stored locally and never sent to third parties.
          </p>
        </div>
      </div>

      <div className="settings-section">
        <h2>Agent Settings</h2>
        <div className="setting-item">
          <label htmlFor="maxSteps">Max Steps</label>
          <input
            id="maxSteps"
            type="number"
            min="1"
            max="20"
            value={settings.maxSteps}
            onChange={(e) => handleChange('maxSteps', parseInt(e.target.value))}
          />
          <p className="setting-hint">
            Maximum number of reasoning steps the agent can take (1-20).
          </p>
        </div>
      </div>

      <div className="settings-section">
        <h2>Appearance</h2>
        <div className="setting-item">
          <label htmlFor="theme">Theme</label>
          <select
            id="theme"
            value={settings.theme}
            onChange={(e) => handleChange('theme', e.target.value)}
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="system">System</option>
          </select>
        </div>
      </div>

      <div className="settings-actions">
        <Button variant="primary" onClick={handleSave}>
          {saved ? 'Saved!' : 'Save Settings'}
        </Button>
        <Button variant="outline" onClick={handleReset}>
          Reset to Defaults
        </Button>
      </div>
    </div>
  )
}
