import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/Card'

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-textSecondary mt-1">Configuration</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Environment</CardTitle>
          <CardDescription>API configuration</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-textSecondary">
            <p>VITE_API_BASE_URL: {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8585'}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
