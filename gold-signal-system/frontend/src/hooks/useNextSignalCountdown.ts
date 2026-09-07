import { useState, useEffect, useRef } from 'react'

export interface NextSignalCountdown {
  remainingSeconds: number
  minutesLeft: number
  secondsLeft: number
  formattedTime: string // "08:42"
  formattedTargetTime: string // "10:00:00 UTC"
  formattedTargetTimeLocal: string // "03:00:00 PM"
  progressPct: number // 0 to 100
  isClose: boolean // true when < 30 seconds remaining
}

export function useNextSignalCountdown(
  timeframeMinutes = 15,
  onCandleClose?: () => void
): NextSignalCountdown {
  const [now, setNow] = useState<Date>(() => new Date())
  const lastTriggeredPeriodRef = useRef<number | null>(null)

  useEffect(() => {
    const timer = setInterval(() => {
      const current = new Date()
      setNow(current)

      // Check if we just crossed into a new candle period
      const currentMinutes = current.getMinutes()
      const currentSeconds = current.getSeconds()
      const currentPeriodIndex = Math.floor(currentMinutes / timeframeMinutes)

      if (
        currentSeconds <= 2 &&
        lastTriggeredPeriodRef.current !== null &&
        lastTriggeredPeriodRef.current !== currentPeriodIndex
      ) {
        lastTriggeredPeriodRef.current = currentPeriodIndex
        if (onCandleClose) {
          // Slight delay (2 seconds) to allow MT5 EA to push new candle to backend
          setTimeout(() => {
            onCandleClose()
          }, 2000)
        }
      } else if (lastTriggeredPeriodRef.current === null) {
        lastTriggeredPeriodRef.current = currentPeriodIndex
      }
    }, 1000)

    return () => clearInterval(timer)
  }, [timeframeMinutes, onCandleClose])

  const currentMinutes = now.getMinutes()
  const currentSeconds = now.getSeconds()

  const totalPeriodSeconds = timeframeMinutes * 60 // 900 seconds for M15
  const elapsedSeconds = (currentMinutes % timeframeMinutes) * 60 + currentSeconds
  const remainingSeconds = Math.max(0, totalPeriodSeconds - elapsedSeconds)

  const minutesLeft = Math.floor(remainingSeconds / 60)
  const secondsLeft = remainingSeconds % 60

  const formattedTime = `${String(minutesLeft).padStart(2, '0')}:${String(secondsLeft).padStart(2, '0')}`

  const targetDate = new Date(now.getTime() + remainingSeconds * 1000)
  targetDate.setSeconds(0, 0)

  const formattedTargetTime =
    targetDate.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    }) + ' UTC'

  const formattedTargetTimeLocal = targetDate.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  const progressPct = Math.min(
    100,
    Math.max(0, (elapsedSeconds / totalPeriodSeconds) * 100)
  )
  const isClose = remainingSeconds <= 30

  return {
    remainingSeconds,
    minutesLeft,
    secondsLeft,
    formattedTime,
    formattedTargetTime,
    formattedTargetTimeLocal,
    progressPct,
    isClose,
  }
}
