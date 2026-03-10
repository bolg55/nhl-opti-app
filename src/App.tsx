import { useCallback, useEffect, useState } from "react"
import { LogOut, Moon, RefreshCw, Sun } from "lucide-react"

import { ConstraintsPanel } from "@/components/constraints-panel"
import { LineupDisplay } from "@/components/lineup-display"
import { LoginForm } from "@/components/login-form"
import { PlayerBrowser } from "@/components/player-browser"
import { SalaryUpload } from "@/components/salary-upload"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { AuthError, checkAuth, logout, refreshData } from "@/lib/api"

export function App() {
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [lockedPlayers, setLockedPlayers] = useState<Set<string>>(
    new Set()
  )
  const [excludedPlayers, setExcludedPlayers] = useState<Set<string>>(
    new Set()
  )
  const [startDate, setStartDate] = useState(
    new Date().toISOString().split("T")[0]
  )
  const [salaryKey, setSalaryKey] = useState(0)
  const [dataVersion, setDataVersion] = useState(0)
  const [apiStatus, setApiStatus] = useState<
    "ok" | "error" | "checking"
  >("checking")
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    checkAuth()
      .then(() => setAuthed(true))
      .catch((e) => {
        if (e instanceof AuthError) setAuthed(false)
        else setAuthed(false)
      })
  }, [])

  useEffect(() => {
    if (!authed) return
    function ping() {
      fetch("/api/health")
        .then((r) => setApiStatus(r.ok ? "ok" : "error"))
        .catch(() => setApiStatus("error"))
    }
    ping()
    const id = setInterval(ping, 30_000)
    return () => clearInterval(id)
  }, [authed])

  const toggleLock = useCallback((key: string) => {
    setLockedPlayers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    setExcludedPlayers((prev) => {
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  const toggleExclude = useCallback((key: string) => {
    setExcludedPlayers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    setLockedPlayers((prev) => {
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await refreshData()
      setDataVersion((v) => v + 1)
    } catch (e) {
      console.error(e)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleLogout() {
    await logout()
    setAuthed(false)
  }

  if (authed === null) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    )
  }

  if (!authed) {
    return <LoginForm onSuccess={() => setAuthed(true)} />
  }

  return (
    <div className="mx-auto flex min-h-svh max-w-5xl flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              apiStatus === "ok"
                ? "bg-green-500"
                : apiStatus === "error"
                  ? "bg-red-500"
                  : "bg-yellow-500"
            }`}
            title={`API ${apiStatus}`}
          />
          <h1 className="text-sm font-medium">NHL Fantasy Optimizer</h1>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh data"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() =>
              setTheme(theme === "dark" ? "light" : "dark")
            }
            title="Toggle theme"
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <ConstraintsPanel
        startDate={startDate}
        onStartDateChange={setStartDate}
        onSettingsSaved={() => {}}
      />

      <main className="flex flex-col gap-6 p-4">
        <SalaryUpload
          key={salaryKey}
          onUploaded={() => {
            setSalaryKey((k) => k + 1)
            setDataVersion((v) => v + 1)
          }}
        />

        <LineupDisplay
          lockedPlayers={lockedPlayers}
          excludedPlayers={excludedPlayers}
          onToggleLock={toggleLock}
          onToggleExclude={toggleExclude}
          startDate={startDate}
        />

        <PlayerBrowser
          lockedPlayers={lockedPlayers}
          excludedPlayers={excludedPlayers}
          onToggleLock={toggleLock}
          onToggleExclude={toggleExclude}
          dataVersion={dataVersion}
        />
      </main>
    </div>
  )
}

export default App
