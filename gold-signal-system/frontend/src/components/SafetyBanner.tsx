import React from 'react'

export const SafetyBanner: React.FC = () => {
  return (
    <aside className="safety-banner" aria-label="Informational Disclaimer">
      <div className="safety-icon" aria-hidden="true">
        ⚠️
      </div>
      <div className="safety-content">
        <h4 className="safety-title">ALERT-ONLY SYSTEM — NO AUTOMATIC TRADING</h4>
        <p className="safety-text">
          This system monitors market conditions and generates notifications only. The user
          must manually analyze the signal and place trades. There are zero buy/sell buttons,
          no auto-trading logic, and no broker execution connected.
        </p>
      </div>
    </aside>
  )
}
