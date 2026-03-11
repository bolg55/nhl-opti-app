import { useState } from "react"
import { Database, Stethoscope } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { triggerInjuryScrape, triggerSalaryScrape } from "@/lib/api"

export function AdminControls({ onRefreshed }: { onRefreshed?: () => void }) {
  const [salaryLoading, setSalaryLoading] = useState(false)
  const [injuryLoading, setInjuryLoading] = useState(false)
  const [message, setMessage] = useState("")

  async function handleSalaryScrape() {
    setSalaryLoading(true)
    setMessage("")
    try {
      const result = await triggerSalaryScrape()
      setMessage(result.message || "Salary scrape complete")
      onRefreshed?.()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Salary scrape failed")
    } finally {
      setSalaryLoading(false)
    }
  }

  async function handleInjuryScrape() {
    setInjuryLoading(true)
    setMessage("")
    try {
      const result = await triggerInjuryScrape()
      setMessage(result.message || "Injury scrape complete")
      onRefreshed?.()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Injury scrape failed")
    } finally {
      setInjuryLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Admin</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleSalaryScrape}
            disabled={salaryLoading}
          >
            <Database className="mr-1.5 h-3.5 w-3.5" />
            {salaryLoading ? "Scraping..." : "Refresh Salaries"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleInjuryScrape}
            disabled={injuryLoading}
          >
            <Stethoscope className="mr-1.5 h-3.5 w-3.5" />
            {injuryLoading ? "Scraping..." : "Refresh Injuries"}
          </Button>
        </div>
        {message && (
          <p className="text-xs font-medium text-muted-foreground">
            {message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
