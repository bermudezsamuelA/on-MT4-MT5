#property copyright "SAMUEL"
#property link      ""
#property version   "1.07"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1 

#property indicator_label1  "Correlacion"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrRed
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

input string SIMBOLO = "EURUSD";

double LineaCorrelacion[];

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, LineaCorrelacion, INDICATOR_DATA);
   ArraySetAsSeries(LineaCorrelacion, true); 
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME, "Correlacion Burbuja " + SIMBOLO);
   return(INIT_SUCCEEDED);
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
   ArraySetAsSeries(time, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);

   int limite_pantalla = (int)ChartGetInteger(0, CHART_FIRST_VISIBLE_BAR);
   if(limite_pantalla <= 0 || limite_pantalla >= rates_total) return(0);

   // 1. Max y Min de tu pantalla actual (Para generar la burbuja simétrica)
   int max_A_idx = ArrayMaximum(high, 0, limite_pantalla + 1);
   int min_A_idx = ArrayMinimum(low, 0, limite_pantalla + 1);
   if(max_A_idx < 0 || min_A_idx < 0) return(0);
   
   double max_A = high[max_A_idx];
   double min_A = low[min_A_idx];

   // 2. Extraer los datos del otro símbolo en ese mismo rango de tiempo
   double high_B[], low_B[];
   datetime start_time = time[limite_pantalla]; 
   datetime end_time = time[0];                 
   
   if(CopyHigh(SIMBOLO, PERIOD_CURRENT, start_time, end_time, high_B) <= 0) return(0);
   if(CopyLow(SIMBOLO, PERIOD_CURRENT, start_time, end_time, low_B) <= 0) return(0);

   int max_B_idx = ArrayMaximum(high_B, 0, WHOLE_ARRAY);
   int min_B_idx = ArrayMinimum(low_B, 0, WHOLE_ARRAY);
   
   double max_B = high_B[max_B_idx];
   double min_B = low_B[min_B_idx];

   if(max_B - min_B == 0) return(0); 

   // Limpiamos la memoria para que no queden líneas rotas
   ArrayInitialize(LineaCorrelacion, EMPTY_VALUE);

   // 3. Normalización global para mantener el desfasaje visual (eje Y separado)
   for(int i = limite_pantalla; i >= 0; i--)
     {
      int shift_B = iBarShift(SIMBOLO, PERIOD_CURRENT, time[i], false);
      if(shift_B >= 0) 
        {
         double close_B = iClose(SIMBOLO, PERIOD_CURRENT, shift_B);
         LineaCorrelacion[i] = ((close_B - min_B) / (max_B - min_B)) * (max_A - min_A) + min_A;
        }
     }

   return(rates_total);
  }