import { useEffect, useState } from "react"
import { ChevronDown, ChevronUp, Save } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getSettings, updateSettings } from "@/lib/api"
import type { Settings } from "@/lib/types"

export function ConstraintsPanel({
  startDate,
  onStartDateChange,
  onSettingsSaved,
}: {
  startDate: string
  onStartDateChange: (date: string) => void
  onSettingsSaved?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings().then(setSettings).catch(console.error)
  }, [])

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setSaved(false)
    try {
      const updated = await updateSettings(settings)
      setSettings(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      onSettingsSaved?.()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  if (!settings) return null

  return (
    <div className="border-b">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50"
      >
        Constraints
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="grid grid-cols-2 gap-4 px-4 pb-4 sm:grid-cols-4">
          <Field
            label="Salary Cap ($M)"
            value={settings.max_cost}
            onChange={(v) =>
              setSettings({ ...settings, max_cost: v })
            }
            step={0.5}
          />
          <Field
            label="Floor %"
            value={settings.min_cost_pct}
            onChange={(v) =>
              setSettings({ ...settings, min_cost_pct: v })
            }
            step={5}
          />
          <Field
            label="Forwards"
            value={settings.num_forwards}
            onChange={(v) =>
              setSettings({ ...settings, num_forwards: v })
            }
            step={1}
          />
          <Field
            label="Defensemen"
            value={settings.num_defensemen}
            onChange={(v) =>
              setSettings({ ...settings, num_defensemen: v })
            }
            step={1}
          />
          <Field
            label="Goalies"
            value={settings.num_goalies}
            onChange={(v) =>
              setSettings({ ...settings, num_goalies: v })
            }
            step={1}
          />
          <Field
            label="Max/Team"
            value={settings.max_per_team}
            onChange={(v) =>
              setSettings({ ...settings, max_per_team: v })
            }
            step={1}
          />
          <Field
            label="Min GP"
            value={settings.min_games_played}
            onChange={(v) =>
              setSettings({ ...settings, min_games_played: v })
            }
            step={1}
          />
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs">Start Date</Label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
            />
          </div>
          <div className="col-span-full flex items-center justify-end gap-2">
            {saved && (
              <span className="text-xs text-primary">Saved!</span>
            )}
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving}
            >
              <Save className="mr-1.5 h-3.5 w-3.5" />
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  step,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  step: number
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  )
}
