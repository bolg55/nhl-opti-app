import { useState } from "react"
import { Lock, Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { optimize } from "@/lib/api"
import type { LineupResult } from "@/lib/types"

export function LineupDisplay({
  lockedPlayers,
  excludedPlayers,
  onToggleLock,
  onToggleExclude,
  startDate,
}: {
  lockedPlayers: Set<string>
  excludedPlayers: Set<string>
  onToggleLock: (name: string) => void
  onToggleExclude: (name: string) => void
  startDate: string
}) {
  const [result, setResult] = useState<LineupResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleOptimize() {
    setLoading(true)
    setError("")
    try {
      const res = await optimize({
        start_date: startDate || undefined,
        locked_players: [...lockedPlayers],
        excluded_players: [...excludedPlayers],
      })
      setResult(res)
      if (!res.feasible) {
        setError(res.message || "No feasible solution found")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Optimization failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button onClick={handleOptimize} disabled={loading}>
          {loading && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
          {loading ? "Optimizing..." : "Optimize"}
        </Button>
        {result?.feasible && (
          <div className="flex gap-4 text-sm text-muted-foreground">
            <span>
              Pts: <strong className="text-foreground">{result.totalPoints}</strong>
            </span>
            <span>
              Salary: <strong className="text-foreground">${result.totalSalary}M</strong>
            </span>
            <span>
              Roster:{" "}
              <strong className="text-foreground">
                {result.players.filter((p) => p.position === "F").length}F /{" "}
                {result.players.filter((p) => p.position === "D").length}D /{" "}
                {result.players.filter((p) => p.position === "G").length}G
              </strong>
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {result?.feasible && result.players.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10"></TableHead>
              <TableHead>Player</TableHead>
              <TableHead>Team</TableHead>
              <TableHead>Pos</TableHead>
              <TableHead className="text-right">GP</TableHead>
              <TableHead className="text-right">Proj Pts</TableHead>
              <TableHead className="text-right">Salary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.players.map((player) => {
              const isLocked = lockedPlayers.has(player.name)
              const isExcluded = excludedPlayers.has(player.name)
              const isGoalie = player.position === "G"
              return (
                <TableRow
                  key={player.name}
                  className={isGoalie ? "text-muted-foreground" : ""}
                >
                  <TableCell className="flex gap-1 px-2">
                    <button
                      onClick={() => onToggleLock(player.name)}
                      className={`p-0.5 ${isLocked ? "text-primary" : "text-muted-foreground/40 hover:text-muted-foreground"}`}
                      title={isLocked ? "Unlock" : "Lock"}
                    >
                      <Lock className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onToggleExclude(player.name)}
                      className={`p-0.5 ${isExcluded ? "text-destructive" : "text-muted-foreground/40 hover:text-muted-foreground"}`}
                      title={isExcluded ? "Include" : "Exclude"}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </TableCell>
                  <TableCell className="font-medium">
                    {player.name}
                    {player.injured && (
                      <Badge
                        variant="destructive"
                        className="ml-2 text-[10px]"
                      >
                        INJ
                      </Badge>
                    )}
                    {isGoalie && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        (team projection)
                      </span>
                    )}
                  </TableCell>
                  <TableCell>{player.team}</TableCell>
                  <TableCell>{player.position}</TableCell>
                  <TableCell className="text-right">
                    {player.gamesThisWeek}
                  </TableCell>
                  <TableCell className="text-right">
                    {player.projFantasyPts}
                  </TableCell>
                  <TableCell className="text-right">
                    {player.salary > 0
                      ? `$${player.salary}M`
                      : "-"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
