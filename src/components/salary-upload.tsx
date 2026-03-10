import { useEffect, useRef, useState } from "react"
import { Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getSalaryStatus, uploadSalary } from "@/lib/api"
import type { SalaryStatus } from "@/lib/types"

export function SalaryUpload({
  onUploaded,
}: {
  onUploaded?: () => void
}) {
  const [status, setStatus] = useState<SalaryStatus | null>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState("")
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getSalaryStatus().then(setStatus).catch(console.error)
  }, [])

  async function handleUpload() {
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setUploading(true)
    setMessage("")
    try {
      const result = await uploadSalary(file)
      setMessage(`Uploaded ${result.count} players`)
      getSalaryStatus().then(setStatus)
      onUploaded?.()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  const hasSalary = status && status.count > 0

  return (
    <Card className={hasSalary ? "" : "border-primary"}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Salary Data</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {status && (
          <p className="text-xs text-muted-foreground">
            {hasSalary
              ? `${status.count} players loaded`
              : "No salary data loaded. Upload a CSV to get started."}
            {status.lastUpdated && (
              <span className="ml-1">
                (updated{" "}
                {new Date(status.lastUpdated).toLocaleDateString()})
              </span>
            )}
          </p>
        )}
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="text-xs file:mr-2 file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-xs file:text-foreground"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={handleUpload}
            disabled={uploading}
          >
            <Upload className="mr-1.5 h-3.5 w-3.5" />
            {uploading ? "Uploading..." : "Upload"}
          </Button>
        </div>
        {message && (
          <p className="text-xs text-muted-foreground">{message}</p>
        )}
      </CardContent>
    </Card>
  )
}
