#property copyright "Tu Nombre"
#property link      ""
#property version   "1.00"

// --- Configuración de la ventana ---
#property indicator_separate_window
#property indicator_buffers 3
#property indicator_plots   3

// Línea principal
#property indicator_label1  "RSI Smooth"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDodgerBlue
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

// Puntos de cimas (Rojos)
#property indicator_label2  "Cimas"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrRed
#property indicator_width2  3

// Puntos de valles (Verdes)
#property indicator_label3  "Valles"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrLime
#property indicator_width3  3

#property indicator_level1 70
#property indicator_level2 30
#property indicator_levelcolor clrGray
#property indicator_levelstyle STYLE_DOT

input int RSI_Period = 14;          
input int Smooth_Period = 5;        
input int Fractal_Bars = 2;         
input int Max_Lookback = 60; 

input int Overbought_Level = 70; 
input int Oversold_Level = 30;   

double MainLineBuffer[]; 
double HighPivots[];     
double LowPivots[];      

// Variables para guardar las "conexiones" a los indicadores nativos
int rsi_handle;
int ma_handle;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, MainLineBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, HighPivots, INDICATOR_DATA);
   SetIndexBuffer(2, LowPivots, INDICATOR_DATA);

   PlotIndexSetInteger(1, PLOT_ARROW, 119);
   PlotIndexSetInteger(2, PLOT_ARROW, 119);

   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, 0.0);

   ArraySetAsSeries(MainLineBuffer, true);
   ArraySetAsSeries(HighPivots, true);
   ArraySetAsSeries(LowPivots, true);

   // --- LA MAGIA DE MQL5 (Piezas Lego) ---
   // 1. Creamos el RSI normal
   rsi_handle = iRSI(_Symbol, PERIOD_CURRENT, RSI_Period, PRICE_CLOSE);
   
   // 2. Creamos la Media Móvil y le pasamos el "rsi_handle" en lugar del precio
   ma_handle = iMA(_Symbol, PERIOD_CURRENT, Smooth_Period, 0, MODE_SMA, rsi_handle);

   IndicatorSetString(INDICATOR_SHORTNAME, "Div MT5");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, "Div_");
   // Liberamos memoria al quitar el indicador
   IndicatorRelease(rsi_handle);
   IndicatorRelease(ma_handle);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < Max_Lookback) return(0);

   ArraySetAsSeries(time, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);

   // Copiamos la data ya procesada y suavizada directamente a nuestro buffer
   if(CopyBuffer(ma_handle, 0, 0, rates_total, MainLineBuffer) <= 0) return(0);

   int limit = rates_total - prev_calculated;
   if(prev_calculated == 0) limit = rates_total - 1;
   if(limit < 0) limit = 0;

   int start_scan = limit;
   if(start_scan >= rates_total - Fractal_Bars) 
      start_scan = rates_total - Fractal_Bars - 1;

   // En MQL5, le decimos que busque la ventana en el gráfico actual (0)
   int subWindow = ChartWindowFind(0, "Div MT5");

   for(int i = start_scan; i >= Fractal_Bars; i--)
     {
      bool isHigh = true;
      bool isLow = true;
      double currentVal = MainLineBuffer[i];

      if(currentVal == 0 || currentVal == EMPTY_VALUE) continue;

      for(int j = 1; j <= Fractal_Bars; j++)
        {
         if(MainLineBuffer[i+j] >= currentVal) isHigh = false;
         if(MainLineBuffer[i+j] <= currentVal) isLow = false;
         if(MainLineBuffer[i-j] >= currentVal) isHigh = false; 
         if(MainLineBuffer[i-j] <= currentVal) isLow = false;
        }

      if(isHigh) HighPivots[i] = currentVal + 2.0; else HighPivots[i] = 0.0;
      if(isLow) LowPivots[i] = currentVal - 2.0; else LowPivots[i] = 0.0;

      // ==========================================
      // MOTOR LÓGICO DE DIVERGENCIAS (MULTINIVEL)
      // ==========================================

      // --- DIVERGENCIA BAJISTA ---
      if(isHigh) 
        {
         for(int k = i + Fractal_Bars + 1; k <= i + Max_Lookback && k < rates_total; k++)
           {
            if(HighPivots[k] > 0.0) 
              {
               if(high[i] > high[k] && currentVal < MainLineBuffer[k])
                 {
                  string nameInd = "Div_Bear_Ind_" + IntegerToString(time[i]);
                  string namePrc = "Div_Bear_Prc_" + IntegerToString(time[i]);

                  color lineColor = (currentVal >= Overbought_Level) ? clrRed : clrOrange;
                  int lineWidth = (currentVal >= Overbought_Level) ? 2 : 1;
                  int lineStyle = (currentVal >= Overbought_Level) ? STYLE_SOLID : STYLE_DOT;

                  ObjectCreate(0, nameInd, OBJ_TREND, subWindow, time[k], MainLineBuffer[k], time[i], currentVal);
                  ObjectSetInteger(0, nameInd, OBJPROP_COLOR, lineColor);
                  ObjectSetInteger(0, nameInd, OBJPROP_STYLE, lineStyle);
                  ObjectSetInteger(0, nameInd, OBJPROP_RAY_RIGHT, false); 
                  ObjectSetInteger(0, nameInd, OBJPROP_WIDTH, lineWidth);

                  ObjectCreate(0, namePrc, OBJ_TREND, 0, time[k], high[k], time[i], high[i]);
                  ObjectSetInteger(0, namePrc, OBJPROP_COLOR, lineColor);
                  ObjectSetInteger(0, namePrc, OBJPROP_STYLE, lineStyle);
                  ObjectSetInteger(0, namePrc, OBJPROP_RAY_RIGHT, false);
                  ObjectSetInteger(0, namePrc, OBJPROP_WIDTH, lineWidth);
                 }
               break; 
              }
           }
        }

      // --- DIVERGENCIA ALCISTA ---
      if(isLow) 
        {
         for(int k = i + Fractal_Bars + 1; k <= i + Max_Lookback && k < rates_total; k++)
           {
            if(LowPivots[k] > 0.0) 
              {
               if(low[i] < low[k] && currentVal > MainLineBuffer[k])
                 {
                  string nameInd = "Div_Bull_Ind_" + IntegerToString(time[i]);
                  string namePrc = "Div_Bull_Prc_" + IntegerToString(time[i]);

                  color lineColor = (currentVal <= Oversold_Level) ? clrLime : clrMagenta;
                  int lineWidth = (currentVal <= Oversold_Level) ? 2 : 1;
                  int lineStyle = (currentVal <= Oversold_Level) ? STYLE_SOLID : STYLE_DOT;

                  ObjectCreate(0, nameInd, OBJ_TREND, subWindow, time[k], MainLineBuffer[k], time[i], currentVal);
                  ObjectSetInteger(0, nameInd, OBJPROP_COLOR, lineColor);
                  ObjectSetInteger(0, nameInd, OBJPROP_STYLE, lineStyle);
                  ObjectSetInteger(0, nameInd, OBJPROP_RAY_RIGHT, false);
                  ObjectSetInteger(0, nameInd, OBJPROP_WIDTH, lineWidth);

                  ObjectCreate(0, namePrc, OBJ_TREND, 0, time[k], low[k], time[i], low[i]);
                  ObjectSetInteger(0, namePrc, OBJPROP_COLOR, lineColor);
                  ObjectSetInteger(0, namePrc, OBJPROP_STYLE, lineStyle);
                  ObjectSetInteger(0, namePrc, OBJPROP_RAY_RIGHT, false);
                  ObjectSetInteger(0, namePrc, OBJPROP_WIDTH, lineWidth);
                 }
               break;
              }
           }
        }
     }

   return(rates_total);
  }