//+------------------------------------------------------------------+
//|                                     MT5_Gold_Signal_Bridge.mq5   |
//|                        XAUUSD Gold Signal Alert System Bridge    |
//|                                  Copyright 2026, Gold System     |
//|                                                                  |
//| Connects your real MT5 broker account directly to your local    |
//| Gold Signal Alert System for 100% genuine real-market data.      |
//+------------------------------------------------------------------+
#property copyright   "XAUUSD Gold Signal Alert System"
#property link        "http://localhost:8000"
#property version     "1.00"
#property description "Streams genuine broker M15 XAUUSD candles directly to your local FastAPI alert system."
#property description "Ensures 100% real data accuracy, zero third-party API costs, and instant Telegram alerts."

//--- Inputs
input group "=== Local Alert Server ==="
input string   InpServerUrl             = "http://127.0.0.1:8000"; // Alert System URL (e.g. http://127.0.0.1:8000)
input string   InpSymbolOverride        = "";                      // Override Symbol (Empty = auto-detect XAUUSD/GOLD)
input bool     InpSendHistoryOnInit     = true;                    // Send recent history on attach to seed indicators
input int      InpHistoryBars           = 100;                     // History bars to seed (50 - 150)

input group "=== Diagnostics & Notifications ==="
input bool     InpShowChartDashboard    = true;                    // Display status dashboard on chart
input bool     InpVerboseLogs           = true;                    // Log detailed WebRequest results to Experts tab

//--- Global state
datetime g_last_bar_time    = 0;
datetime g_last_sent_bar    = 0;
double   g_last_sent_price  = 0.0;
int      g_candles_sent     = 0;
string   g_status_msg       = "Initializing...";
color    g_status_color     = clrYellow;

//+------------------------------------------------------------------+
//| Helper: Normalize broker symbol name (e.g. XAUUSDm -> XAUUSD)    |
//+------------------------------------------------------------------+
string GetNormalizedSymbol(string sym)
{
   if(StringLen(InpSymbolOverride) > 0)
      return InpSymbolOverride;

   string upper = sym;
   StringToUpper(upper);

   if(StringFind(upper, "XAU") >= 0 || StringFind(upper, "GOLD") >= 0)
      return "XAUUSD";

   return upper;
}

//+------------------------------------------------------------------+
//| Helper: Convert MT5 timeframe enum to standard string            |
//+------------------------------------------------------------------+
string GetTimeframeString(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      default:         return "M15";
   }
}

//+------------------------------------------------------------------+
//| Helper: Format datetime to ISO 8601 string (UTC)                 |
//+------------------------------------------------------------------+
string FormatISOTime(datetime t)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
}

//+------------------------------------------------------------------+
//| Helper: Build JSON string for a single candle                    |
//+------------------------------------------------------------------+
string BuildCandleJson(string symbol, string timeframe, datetime bar_time,
                       double o, double h, double l, double c, long v)
{
   return StringFormat(
      "{\"symbol\":\"%s\",\"timeframe\":\"%s\",\"timestamp\":\"%s\",\"open\":%.2f,\"high\":%.2f,\"low\":%.2f,\"close\":%.2f,\"volume\":%d}",
      symbol, timeframe, FormatISOTime(bar_time), o, h, l, c, v
   );
}

//+------------------------------------------------------------------+
//| Update visual status dashboard on chart                          |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   if(!InpShowChartDashboard) return;

   string broker_info = AccountInfoString(ACCOUNT_COMPANY);
   long   acc_num     = AccountInfoInteger(ACCOUNT_LOGIN);
   string norm_sym    = GetNormalizedSymbol(_Symbol);
   string tf_str      = GetTimeframeString(_Period);

   string text = "=======================================================\n";
   text += "  🏆 XAUUSD GOLD SIGNAL SYSTEM — MT5 LIVE BRIDGE\n";
   text += "=======================================================\n";
   text += StringFormat("  Account:      #%d (%s)\n", acc_num, broker_info);
   text += StringFormat("  Chart Symbol: %s  ->  Normalized: %s\n", _Symbol, norm_sym);
   text += StringFormat("  Timeframe:    %s\n", tf_str);
   text += StringFormat("  Server URL:   %s\n", InpServerUrl);
   text += "-------------------------------------------------------\n";
   text += StringFormat("  Bridge Status: %s\n", g_status_msg);
   text += StringFormat("  Candles Sent:  %d\n", g_candles_sent);
   if(g_last_sent_bar > 0)
   {
      text += StringFormat("  Last Sent Bar: %s  |  Close: %.2f\n",
                           TimeToString(g_last_sent_bar, TIME_DATE|TIME_MINUTES), g_last_sent_price);
   }
   text += "=======================================================\n";
   text += "  Status: Live Real-Market Feed Active\n";
   text += "=======================================================";

   Comment(text);
}

//+------------------------------------------------------------------+
//| Send completed candle (shift = 1) to FastAPI backend             |
//+------------------------------------------------------------------+
bool SendCompletedCandle(int shift = 1)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, shift, 1, rates);
   if(copied < 1)
   {
      Print("❌ [MT5 Bridge] Failed to copy rates for bar ", shift);
      return false;
   }

   string sym  = GetNormalizedSymbol(_Symbol);
   string tf   = GetTimeframeString(_Period);
   string json = BuildCandleJson(sym, tf, rates[0].time, rates[0].open,
                                 rates[0].high, rates[0].low, rates[0].close,
                                 rates[0].tick_volume);

   char post_data[];
   int len = StringToCharArray(json, post_data, 0, WHOLE_ARRAY, CP_UTF8);
   if(len > 0 && post_data[len - 1] == 0)
      ArrayResize(post_data, len - 1);

   char result[];
   string result_headers;
   string url = InpServerUrl + "/api/market/candle";
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";

   ResetLastError();
   int http_res = WebRequest("POST", url, headers, 4000, post_data, result, result_headers);

   if(http_res == 200)
   {
      g_candles_sent++;
      g_last_sent_bar   = rates[0].time;
      g_last_sent_price = rates[0].close;
      g_status_msg      = "Connected & Streaming ✅";
      UpdateDashboard();

      if(InpVerboseLogs)
      {
         PrintFormat("✅ [MT5 Bridge] Sent M15 candle: %s | O:%.2f H:%.2f L:%.2f C:%.2f",
                     TimeToString(rates[0].time, TIME_DATE|TIME_MINUTES),
                     rates[0].open, rates[0].high, rates[0].low, rates[0].close);
      }
      return true;
   }
   else
   {
      int err = GetLastError();
      if(err == 4014) // ERR_FUNCTION_NOT_ALLOWED
      {
         g_status_msg = "WebRequest Forbidden! (Add URL in MT5 Options)";
         PrintFormat("❌ [MT5 Bridge] ERROR 4014: WebRequest not allowed!");
         PrintFormat("👉 Solution: In MT5, go to Tools -> Options -> Expert Advisors");
         PrintFormat("👉 Check 'Allow WebRequest for listed URL' and add: %s", InpServerUrl);
      }
      else
      {
         g_status_msg = StringFormat("HTTP Error %d (MT5 Error %d)", http_res, err);
         PrintFormat("⚠️ [MT5 Bridge] WebRequest failed. HTTP: %d, MT5 Error: %d", http_res, err);
      }
      UpdateDashboard();
      return false;
   }
}

//+------------------------------------------------------------------+
//| Backfill recent historical candles to seed indicator warm-up     |
//+------------------------------------------------------------------+
void BackfillHistory(int bars_count)
{
   if(bars_count <= 0) return;
   if(bars_count > 150) bars_count = 150;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, 1, bars_count, rates);
   if(copied < 1)
   {
      Print("❌ [MT5 Bridge] Failed to copy historical rates for seeding");
      return;
   }

   string sym = GetNormalizedSymbol(_Symbol);
   string tf  = GetTimeframeString(_Period);

   // Build history JSON array (chronological order: oldest to newest)
   string json = "{\"symbol\":\"" + sym + "\",\"timeframe\":\"" + tf + "\",\"candles\":[";
   for(int i = copied - 1; i >= 0; i--)
   {
      string c_json = BuildCandleJson(sym, tf, rates[i].time, rates[i].open,
                                     rates[i].high, rates[i].low, rates[i].close,
                                     rates[i].tick_volume);
      json += c_json;
      if(i > 0) json += ",";
   }
   json += "]}";

   char post_data[];
   int len = StringToCharArray(json, post_data, 0, WHOLE_ARRAY, CP_UTF8);
   if(len > 0 && post_data[len - 1] == 0)
      ArrayResize(post_data, len - 1);

   char result[];
   string result_headers;
   string url = InpServerUrl + "/api/market/history";
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";

   ResetLastError();
   PrintFormat("⏳ [MT5 Bridge] Seeding %d historical bars to %s...", copied, url);
   int http_res = WebRequest("POST", url, headers, 8000, post_data, result, result_headers);

   if(http_res == 200)
   {
      g_status_msg = StringFormat("Seeded %d bars ✅ | Waiting for next candle", copied);
      PrintFormat("✅ [MT5 Bridge] History seeding successful! (%d bars)", copied);
      UpdateDashboard();
   }
   else
   {
      int err = GetLastError();
      if(err == 4014)
      {
         g_status_msg = "WebRequest Forbidden! (Add URL in MT5 Options)";
         PrintFormat("❌ [MT5 Bridge] ERROR 4014: WebRequest not allowed for %s", InpServerUrl);
      }
      else
      {
         g_status_msg = StringFormat("History Seed Failed (HTTP %d, Err %d)", http_res, err);
         PrintFormat("⚠️ [MT5 Bridge] History seeding failed. HTTP: %d, Err: %d", http_res, err);
      }
      UpdateDashboard();
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_last_bar_time   = 0;
   g_candles_sent    = 0;
   g_last_sent_bar   = 0;
   g_last_sent_price = 0.0;
   g_status_msg      = "Connecting...";

   Print("===============================================================");
   Print("🚀 [MT5 Bridge] Starting Gold Signal Alert System Bridge EA");
   PrintFormat("   Broker: %s | Account: %d", AccountInfoString(ACCOUNT_COMPANY), AccountInfoInteger(ACCOUNT_LOGIN));
   PrintFormat("   Chart: %s %s | Target URL: %s", _Symbol, GetTimeframeString(_Period), InpServerUrl);
   Print("===============================================================");

   // Initial bar sync
   g_last_bar_time = iTime(_Symbol, _Period, 0);

   // Backfill historical bars if enabled
   if(InpSendHistoryOnInit)
   {
      BackfillHistory(InpHistoryBars);
   }
   else
   {
      g_status_msg = "Active | Waiting for next candle close";
      UpdateDashboard();
   }

   // 5-second timer for chart clock updates
   EventSetTimer(5);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
   Print("🛑 [MT5 Bridge] Bridge stopped (Reason: ", reason, ")");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == 0) return;

   // First tick after initial attach
   if(g_last_bar_time == 0)
   {
      g_last_bar_time = current_bar_time;
      UpdateDashboard();
      return;
   }

   // Detect candle transition: Bar 0 changed -> Bar 1 has CLOSED!
   if(current_bar_time != g_last_bar_time)
   {
      g_last_bar_time = current_bar_time;

      if(InpVerboseLogs)
      {
         PrintFormat("🔔 [MT5 Bridge] New %s candle detected at %s! Dispatching closed bar 1...",
                     GetTimeframeString(_Period), TimeToString(current_bar_time));
      }

      // Send the newly closed candle (Bar 1)
      SendCompletedCandle(1);
   }
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   UpdateDashboard();
}
//+------------------------------------------------------------------+
