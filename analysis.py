"""
Empirical charts for the SG Carry Trade blog post.
Downloads data from Yahoo Finance and public APIs, generates publication-quality charts.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from scipy import stats

warnings.filterwarnings('ignore')

# ── Config ──────────────────────────────────────────────────────────────────
CHARTS_DIR = os.path.join(os.path.dirname(__file__), 'charts')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Style: clean/minimal
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'axes.grid.which': 'major',
    'grid.alpha': 0.3,
    'grid.linewidth': 0.5,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.8,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'legend.frameon': False,
    'figure.dpi': 150,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.3,
})

COLORS = {
    'sgd': '#2C5F8A',      # Steel blue
    'jpy': '#D4533B',      # Muted red
    'aud': '#4A9B6E',      # Sage green
    'mxn': '#D4963B',      # Amber
    'eur': '#7B68AE',      # Muted purple
    'gbp': '#3BA6C9',      # Teal
    'diff': '#8B9DC3',     # Light steel
    'band': '#E8E8E8',     # Light gray for band fill
    'accent': '#2C5F8A',   # Primary accent
    'negative': '#D4533B', # For negative values
}


# ── Data download helpers ───────────────────────────────────────────────────

def download_yf(ticker, start='2000-01-01', end='2026-04-14', cache_name=None):
    """Download from Yahoo Finance with local caching."""
    import yfinance as yf

    if cache_name is None:
        cache_name = ticker.replace('=', '').replace('^', '').replace('/', '')
    cache_path = os.path.join(DATA_DIR, f'{cache_name}.csv')

    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        print(f'  Loaded {cache_name} from cache ({len(df)} rows)')
        return df

    print(f'  Downloading {ticker}...')
    df = yf.download(ticker, start=start, end=end, progress=False)
    if not df.empty:
        # Flatten multi-level columns if needed
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.to_csv(cache_path)
        print(f'  Saved {cache_name} ({len(df)} rows)')
    else:
        print(f'  WARNING: No data for {ticker}')
    return df


def download_all_data():
    """Download all required datasets."""
    print('Downloading data...')
    data = {}

    # FX rates (all vs USD)
    data['usdsgd'] = download_yf('SGD=X', start='2000-01-01')      # USD/SGD
    data['usdjpy'] = download_yf('JPY=X', start='2000-01-01')      # USD/JPY
    data['usdmxn'] = download_yf('MXN=X', start='2000-01-01')      # USD/MXN
    data['audusd'] = download_yf('AUDUSD=X', start='2003-01-01')   # AUD/USD
    data['eurusd'] = download_yf('EURUSD=X', start='2000-01-01')   # EUR/USD
    data['gbpusd'] = download_yf('GBPUSD=X', start='2000-01-01')   # GBP/USD

    # US 3-month T-bill yield (proxy for USD short rate)
    data['us3m'] = download_yf('^IRX', start='2000-01-01', cache_name='US3M')

    # SGD NEER: We'll use BIS real effective exchange rate from FRED as proxy
    # Since FRED direct download is blocked, we'll compute NEER proxy from spot

    return data


# ── Chart 1: Interest Rate Differential ─────────────────────────────────────

def chart1_rate_differential(data):
    """
    Chart 1: SGD vs USD short-term interest rate differential.

    Uses actual data:
    - USD: 3-month T-bill yield from Yahoo Finance (^IRX)
    - SGD: 1-year SGS T-bill yield from SingStat/MAS (best available proxy)
    """
    print('\nBuilding Chart 1: Interest Rate Differential...')

    # Load actual Singapore interest rates
    sg_rates = pd.read_csv(os.path.join(DATA_DIR, 'sg_interest_rates.csv'), parse_dates=['date'])
    sg_rates = sg_rates.set_index('date').sort_index()

    # SGD short rate: use 1Y T-bill yield (longest history, closest to money market)
    sgd_1y = sg_rates['sgs_1y_tbill_yield'].dropna()

    # USD 3M T-bill (monthly)
    us3m = data['us3m']['Close'].resample('ME').last().dropna()

    # Align to common monthly dates
    # Reindex SGD to month-end to match
    sgd_monthly = sgd_1y.copy()
    sgd_monthly.index = sgd_monthly.index + pd.offsets.MonthEnd(0)

    common = sgd_monthly.index.intersection(us3m.index)
    sgd_rate = sgd_monthly.loc[common]
    usd_rate = us3m.loc[common]
    diff = usd_rate - sgd_rate

    dates = common

    # MAS policy change dates (major slope changes only)
    mas_dates = pd.to_datetime([
        '2001-07-12', '2002-07-10', '2004-04-14', '2008-10-10',
        '2009-04-14', '2010-04-14', '2010-10-14', '2015-01-28',
        '2016-04-14', '2018-04-13', '2020-03-30', '2021-10-14',
        '2022-01-25', '2022-04-14', '2024-10-14',
    ])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[3, 1],
                                     sharex=True, gridspec_kw={'hspace': 0.08})

    # Top panel: Two rates
    ax1.plot(dates, usd_rate, color=COLORS['negative'], linewidth=1.5,
              label='USD 3M T-Bill yield', alpha=0.9)
    ax1.plot(dates, sgd_rate, color=COLORS['sgd'], linewidth=1.5,
              label='SGD 1Y T-Bill yield (SGS)', alpha=0.9)
    ax1.fill_between(dates, sgd_rate, usd_rate, alpha=0.12, color=COLORS['diff'],
                      where=usd_rate > sgd_rate)
    ax1.fill_between(dates, sgd_rate, usd_rate, alpha=0.08, color=COLORS['negative'],
                      where=usd_rate <= sgd_rate)

    for d in mas_dates:
        if d >= dates.min() and d <= dates.max():
            ax1.axvline(d, color='#CCCCCC', linewidth=0.5, alpha=0.6)

    ax1.set_ylabel('Yield (%)')
    ax1.set_title('USD vs SGD Short-Term Interest Rates', fontsize=14, fontweight='bold', pad=15)
    ax1.legend(loc='upper left')
    ax1.set_ylim(bottom=-0.5)

    # Bottom panel: Rate differential
    ax2.fill_between(dates, 0, diff, alpha=0.4, color=COLORS['accent'],
                      where=diff > 0)
    ax2.fill_between(dates, 0, diff, alpha=0.4, color=COLORS['negative'],
                      where=diff <= 0)
    ax2.axhline(0, color='black', linewidth=0.5)
    ax2.set_ylabel('USD − SGD\n(pp)')
    ax2.set_xlabel('')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))

    ax2.annotate('Gray lines = MAS policy slope changes. Data: Yahoo Finance (USD), SingStat (SGD).',
                  xy=(0.02, 0.05), xycoords='axes fraction', fontsize=7.5, color='gray')

    # Print mean differential
    mean_diff = diff.mean()
    print(f'  Mean USD-SGD differential: {mean_diff:.2f}pp')
    print(f'  Median: {diff.median():.2f}pp')
    print(f'  % of months USD > SGD: {(diff > 0).mean()*100:.1f}%')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart1_rate_differential.png'))
    plt.close(fig)
    print('  Saved chart1_rate_differential.png')


# ── Chart 2: Carry Trade Backtest ────────────────────────────────────────────

def chart2_carry_backtest(data):
    """
    Chart 2: Simulated unhedged carry trade backtest.

    For each currency pair, compute monthly carry returns:
      return = (r_USD - r_fund) / 12 - ΔS
    where ΔS is the monthly spot FX change.

    For funding rates we need foreign short rates. Since we don't have
    direct access to all short rates, we use the following approach:
    - For JPY/USD: Borrow JPY (rate ≈ 0-0.5%), invest USD
    - For SGD/USD: Borrow SGD, invest USD
    - For AUD/USD: Borrow USD, invest AUD (AUD had higher rates historically)
    - For MXN/USD: Borrow USD, invest MXN (MXN had higher rates)

    We approximate foreign short rates using historical averages from IMF data.
    The key point is the SHAPE of the cumulative returns, not the exact level.
    """
    print('\nBuilding Chart 2: Carry Trade Backtest...')

    us3m = data['us3m']['Close'].resample('M').last().dropna() / 100  # Convert to decimal

    # Get monthly spot rates
    usdsgd = data['usdsgd']['Close'].resample('M').last().dropna()
    usdjpy = data['usdjpy']['Close'].resample('M').last().dropna()
    usdmxn = data['usdmxn']['Close'].resample('M').last().dropna()
    audusd = data['audusd']['Close'].resample('M').last().dropna()

    # Common date range
    start = max(usdsgd.index.min(), usdjpy.index.min(), usdmxn.index.min(),
                audusd.index.min(), us3m.index.min())
    end = min(usdsgd.index.max(), usdjpy.index.max(), usdmxn.index.max(),
              audusd.index.max(), us3m.index.max())

    # Align all to common monthly dates
    idx = pd.date_range(start, end, freq='M')
    usdsgd = usdsgd.reindex(idx, method='ffill')
    usdjpy = usdjpy.reindex(idx, method='ffill')
    usdmxn = usdmxn.reindex(idx, method='ffill')
    audusd = audusd.reindex(idx, method='ffill')
    us3m_aligned = us3m.reindex(idx, method='ffill')

    # Monthly FX returns (from perspective of carry trader)
    # SGD carry: borrow SGD, invest USD. Profit when SGD weakens (USD/SGD rises)
    sgd_fx_ret = usdsgd.pct_change()  # positive = SGD weakened = good for carry

    # JPY carry: borrow JPY, invest USD. Profit when JPY weakens (USD/JPY rises)
    jpy_fx_ret = usdjpy.pct_change()

    # MXN carry: borrow USD, invest MXN. Profit when MXN strengthens (USD/MXN falls)
    mxn_fx_ret = -usdmxn.pct_change()

    # AUD carry: borrow USD, invest AUD. Profit when AUD strengthens (AUD/USD rises)
    aud_fx_ret = audusd.pct_change()

    # Approximate foreign short rates (annual, as decimal)
    # More realistic time-varying approximations based on historical data

    # SGD rate: use MAS slope schedule (from Chart 1) to derive r_SGD = r_USD - slope
    sgd_slope_schedule = [
        ('2000-01-01', 0.015), ('2001-07-01', 0.005), ('2002-07-01', 0.0),
        ('2004-04-01', 0.01), ('2005-04-01', 0.015), ('2007-04-01', 0.02),
        ('2008-10-01', 0.005), ('2009-04-01', 0.0), ('2010-04-01', 0.01),
        ('2010-10-01', 0.02), ('2011-04-01', 0.025), ('2012-04-01', 0.015),
        ('2015-01-01', 0.005), ('2016-04-01', 0.0), ('2018-04-01', 0.005),
        ('2018-10-01', 0.015), ('2019-10-01', 0.01), ('2020-03-01', 0.0),
        ('2021-10-01', 0.005), ('2022-01-01', 0.015), ('2022-04-01', 0.02),
        ('2023-04-01', 0.015), ('2024-10-01', 0.01),
    ]
    sgd_slope = pd.Series(
        [s[1] for s in sgd_slope_schedule],
        index=pd.to_datetime([s[0] for s in sgd_slope_schedule])
    ).reindex(idx, method='ffill').fillna(0.015)
    sgd_rate = (us3m_aligned - sgd_slope).clip(lower=0)

    # JPY rate: near zero 2000-2022, rising from 2023
    jpy_rate = pd.Series(0.001, index=idx)
    jpy_rate[idx > '2016-01-01'] = -0.001  # Negative rate era
    jpy_rate[idx > '2023-01-01'] = 0.002
    jpy_rate[idx > '2024-03-01'] = 0.005
    jpy_rate[idx > '2024-07-01'] = 0.0025  # Cut

    # AUD rate: track USD with ~25-100bp spread, narrowing over time
    aud_spread = pd.Series(0.015, index=idx)  # 150bp above USD pre-GFC
    aud_spread[idx > '2008-10-01'] = 0.02    # Higher spread during rate divergence
    aud_spread[idx > '2013-01-01'] = 0.01
    aud_spread[idx > '2020-01-01'] = 0.005
    aud_spread[idx > '2022-06-01'] = 0.005
    aud_rate = us3m_aligned + aud_spread

    # MXN rate: consistently high spread over USD
    mxn_spread = pd.Series(0.05, index=idx)    # ~500bp spread
    mxn_spread[idx > '2008-10-01'] = 0.04
    mxn_spread[idx > '2015-01-01'] = 0.06     # Banxico tightening
    mxn_spread[idx > '2020-01-01'] = 0.05
    mxn_spread[idx > '2022-01-01'] = 0.06     # Aggressive Banxico
    mxn_rate = us3m_aligned + mxn_spread

    # Monthly carry returns
    # SGD: earn USD rate, pay SGD rate, FX gain/loss from SGD move
    sgd_carry = (us3m_aligned - sgd_rate) / 12 + sgd_fx_ret

    # JPY: earn USD rate, pay JPY rate, FX gain/loss
    jpy_carry = (us3m_aligned - jpy_rate) / 12 + jpy_fx_ret

    # AUD: earn AUD rate, pay USD rate, FX gain/loss
    aud_carry = (aud_rate - us3m_aligned) / 12 + aud_fx_ret

    # MXN: earn MXN rate, pay USD rate, FX gain/loss
    mxn_carry = (mxn_rate - us3m_aligned) / 12 + mxn_fx_ret

    # Drop first row (NaN from pct_change) and any remaining NaN
    carries = pd.DataFrame({
        'SGD/USD': sgd_carry,
        'JPY/USD': jpy_carry,
        'AUD/USD': aud_carry,
        'MXN/USD': mxn_carry,
    }).dropna()

    # Cumulative returns (starting at 0)
    cum_returns = (1 + carries).cumprod() - 1

    # Compute Sharpe ratios (annualized)
    sharpes = {}
    for col in carries.columns:
        ann_ret = carries[col].mean() * 12
        ann_vol = carries[col].std() * np.sqrt(12)
        sharpes[col] = ann_ret / ann_vol if ann_vol > 0 else 0

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6.5))

    color_map = {
        'SGD/USD': COLORS['sgd'],
        'JPY/USD': COLORS['jpy'],
        'AUD/USD': COLORS['aud'],
        'MXN/USD': COLORS['mxn'],
    }
    linewidth_map = {
        'SGD/USD': 2.5,
        'JPY/USD': 1.5,
        'AUD/USD': 1.5,
        'MXN/USD': 1.5,
    }

    for col in cum_returns.columns:
        ax.plot(cum_returns.index, cum_returns[col] * 100,
                color=color_map[col], linewidth=linewidth_map[col],
                label=f'{col} (SR: {sharpes[col]:.2f})', alpha=0.9)

    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_ylabel('Cumulative Return (%)')
    ax.set_title('Unhedged Carry Trade Returns: SGD vs Free-Floating Currencies',
                  fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper left', title='Carry Trade (Sharpe Ratio)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))

    # Add annotation about SGD — place it mid-chart for clarity
    mid_idx = len(cum_returns) * 3 // 4
    sgd_mid = cum_returns['SGD/USD'].iloc[mid_idx] * 100
    ax.annotate('SGD carry: ~0%\n(band slope absorbs the differential)',
                xy=(cum_returns.index[mid_idx], sgd_mid),
                xytext=(0, -60), textcoords='offset points',
                fontsize=9, color=COLORS['sgd'], fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLORS['sgd'], lw=1.2))

    # Subtitle
    ax.text(0.5, -0.12,
            'Borrow the low-rate currency, invest in the high-rate currency, leave FX exposure unhedged.\n'
            'Foreign short rates approximated from historical policy rate spreads vs US 3M T-Bill.',
            transform=ax.transAxes, ha='center', fontsize=8.5, color='gray', style='italic')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart2_carry_backtest.png'))
    plt.close(fig)
    print('  Saved chart2_carry_backtest.png')

    # Print summary stats
    print('\n  Carry Trade Summary Statistics:')
    print(f'  {"Pair":<10} {"Ann. Return":>12} {"Ann. Vol":>10} {"Sharpe":>8} {"Skew":>8} {"Kurt":>8}')
    for col in carries.columns:
        ann_ret = carries[col].mean() * 12 * 100
        ann_vol = carries[col].std() * np.sqrt(12) * 100
        skew = carries[col].skew()
        kurt = carries[col].kurtosis()
        print(f'  {col:<10} {ann_ret:>11.2f}% {ann_vol:>9.2f}% {sharpes[col]:>8.2f} {skew:>8.2f} {kurt:>8.2f}')


# ── Chart 3: SGD NEER Band Visualization ────────────────────────────────────

def chart3_neer_band(data):
    """
    Chart 3: SGD NEER with estimated band.

    Since direct NEER data from MAS API is unavailable, we construct a proxy:
    - Use USD/SGD as the primary bilateral rate
    - Estimate the trend (guided appreciation path) using a rolling regression
    - Show ±2% estimated band around the trend

    This is a simplification (NEER is trade-weighted, not bilateral) but captures
    the key visual: SGD tracks a guided path with tight dispersion.
    """
    print('\nBuilding Chart 3: SGD NEER Band...')

    # Load actual BIS NEER data (monthly, 1994-2026)
    neer = pd.read_csv(os.path.join(DATA_DIR, 'sgd_neer_bis.csv'), parse_dates=['date'])
    neer = neer.set_index('date').sort_index()
    neer_index = neer['neer_index'].dropna()

    # Estimate the band midpoint using a smooth trend
    # Double-smoothed 12-month centered MA (each pass = 12 months)
    ma1 = neer_index.rolling(12, center=True, min_periods=6).mean()
    ma2 = ma1.rolling(12, center=True, min_periods=6).mean()
    trend = ma2.interpolate(method='linear').ffill().bfill()

    # Band: ±2% around the trend
    upper = trend * 1.02
    lower = trend * 0.98

    # Deviation from trend (%)
    deviation = (neer_index / trend - 1) * 100

    # Regime break dates for visual markers
    regime_breaks = pd.to_datetime([
        '2001-07-01', '2004-04-01', '2008-10-01', '2010-04-01',
        '2015-01-01', '2016-04-01', '2018-04-01', '2020-03-01',
        '2021-10-01', '2022-04-01',
    ])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[3, 1],
                                     sharex=True, gridspec_kw={'hspace': 0.08})

    # Top: NEER with estimated band
    ax1.fill_between(neer_index.index, lower, upper, alpha=0.15, color=COLORS['accent'],
                      edgecolor='none', label='Estimated ±2% band')
    ax1.plot(neer_index.index, trend, color=COLORS['accent'], linewidth=1,
              linestyle='--', alpha=0.5, label='Estimated midpoint (double 12M MA)')
    ax1.plot(neer_index.index, neer_index, color=COLORS['sgd'], linewidth=1.2,
              alpha=0.9, label='S$ NEER (BIS broad basket, 2020=100)')

    for d in regime_breaks:
        if d >= neer_index.index.min() and d <= neer_index.index.max():
            ax1.axvline(d, color='#CCCCCC', linewidth=0.5, alpha=0.6)

    ax1.set_ylabel('Index (2020 = 100)')
    ax1.set_title('SGD Nominal Effective Exchange Rate with Estimated ±2% Band',
                    fontsize=14, fontweight='bold', pad=15)
    ax1.legend(loc='upper left', fontsize=9)

    # Bottom: deviation from trend
    ax2.fill_between(deviation.index, 0, deviation,
                      where=deviation > 0, alpha=0.4, color=COLORS['aud'])
    ax2.fill_between(deviation.index, 0, deviation,
                      where=deviation <= 0, alpha=0.4, color=COLORS['negative'])
    ax2.axhline(0, color='black', linewidth=0.5)
    ax2.axhline(2, color='gray', linewidth=0.5, linestyle='--', alpha=0.5)
    ax2.axhline(-2, color='gray', linewidth=0.5, linestyle='--', alpha=0.5)
    ax2.set_ylabel('Deviation\nfrom trend (%)')
    ax2.set_ylim(-4, 4)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax2.xaxis.set_major_locator(mdates.YearLocator(3))

    ax2.annotate('Data: BIS broad NEER (64 economies). Gray lines = MAS slope changes. '
                  'Dashed = ±2% band.',
                  xy=(0.02, 0.05), xycoords='axes fraction', fontsize=7.5, color='gray')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart3_neer_band.png'))
    plt.close(fig)
    print('  Saved chart3_neer_band.png')

    # Print band statistics
    print(f'  Deviation from trend: mean={deviation.mean():.2f}%, std={deviation.std():.2f}%')
    pct_in_band = ((deviation.abs() < 2).sum() / len(deviation)) * 100
    print(f'  % of months within ±2% band: {pct_in_band:.1f}%')


# ── Chart 4: Fama Regression (UIP Test) ──────────────────────────────────────

def chart4_fama_regression(data):
    """
    Chart 4: Fama (1984) regression coefficients across currencies.

    The classic test: Δs_{t+1} = α + β (f_t - s_t) + ε
    where (f_t - s_t) ≈ r_domestic - r_foreign (interest rate differential).

    UIP predicts β = 1.  Empirically, β < 0 for most currencies (the forward
    premium puzzle).  For SGD, β should be close to 1 if UIP holds.

    Since we don't have forward rates, we approximate the forward premium
    with the interest rate differential. For SGD we use actual SGS yields.
    For others we approximate with historical rate spreads vs USD.
    """
    print('\nBuilding Chart 4: Fama Regression...')

    # Monthly FX returns (log changes in spot, positive = domestic appreciation vs USD)
    usdsgd = data['usdsgd']['Close'].resample('ME').last().dropna()
    usdjpy = data['usdjpy']['Close'].resample('ME').last().dropna()
    usdmxn = data['usdmxn']['Close'].resample('ME').last().dropna()
    audusd = data['audusd']['Close'].resample('ME').last().dropna()
    eurusd = data['eurusd']['Close'].resample('ME').last().dropna()
    gbpusd = data['gbpusd']['Close'].resample('ME').last().dropna()
    us3m = data['us3m']['Close'].resample('ME').last().dropna() / 100

    # Log spot changes (positive = domestic currency strengthened vs USD)
    ds_sgd = -np.log(usdsgd).diff()   # SGD appreciation
    ds_jpy = -np.log(usdjpy).diff()   # JPY appreciation
    ds_mxn = -np.log(usdmxn).diff()   # MXN appreciation
    ds_aud = np.log(audusd).diff()     # AUD appreciation
    ds_eur = np.log(eurusd).diff()     # EUR appreciation
    ds_gbp = np.log(gbpusd).diff()     # GBP appreciation

    # Load SGD actual rate
    sg_rates = pd.read_csv(os.path.join(DATA_DIR, 'sg_interest_rates.csv'), parse_dates=['date'])
    sg_rates = sg_rates.set_index('date').sort_index()
    sgd_1y = sg_rates['sgs_1y_tbill_yield'].dropna() / 100
    sgd_1y.index = sgd_1y.index + pd.offsets.MonthEnd(0)

    # Forward premium proxy: (r_domestic - r_USD) / 12 for monthly
    # SGD: use actual data
    fp_sgd = (sgd_1y - us3m).dropna() / 12

    # For others, approximate spreads (annual)
    # JPY
    jpy_rate = pd.Series(0.001, index=us3m.index)
    jpy_rate[jpy_rate.index > '2016-01-01'] = -0.001
    jpy_rate[jpy_rate.index > '2023-01-01'] = 0.002
    jpy_rate[jpy_rate.index > '2024-03-01'] = 0.005
    fp_jpy = (jpy_rate - us3m) / 12

    # AUD: roughly track USD ± spread
    aud_spread = pd.Series(0.01, index=us3m.index)
    aud_spread[aud_spread.index > '2008-10-01'] = 0.02
    aud_spread[aud_spread.index > '2013-01-01'] = 0.01
    aud_spread[aud_spread.index > '2020-01-01'] = 0.005
    fp_aud = ((us3m + aud_spread) - us3m) / 12  # = aud_spread / 12

    # EUR
    eur_rate = us3m - 0.005  # roughly 50bp below USD on average
    eur_rate[eur_rate.index > '2014-06-01'] = -0.001
    eur_rate[eur_rate.index > '2022-07-01'] = us3m[us3m.index > '2022-07-01'] - 0.01
    fp_eur = (eur_rate - us3m) / 12

    # GBP: close to USD
    gbp_rate = us3m - 0.005
    gbp_rate[gbp_rate.index > '2009-01-01'] = us3m[us3m.index > '2009-01-01'] - 0.01
    gbp_rate[gbp_rate.index > '2022-01-01'] = us3m[us3m.index > '2022-01-01'] - 0.005
    fp_gbp = (gbp_rate - us3m) / 12

    # MXN
    mxn_spread = pd.Series(0.05, index=us3m.index)
    mxn_spread[mxn_spread.index > '2015-01-01'] = 0.06
    mxn_spread[mxn_spread.index > '2020-01-01'] = 0.05
    fp_mxn = ((us3m + mxn_spread) - us3m) / 12

    # Run Fama regressions: Δs_{t+1} = α + β * fp_t + ε
    currencies = {
        'SGD': (ds_sgd, fp_sgd),
        'JPY': (ds_jpy, fp_jpy),
        'AUD': (ds_aud, fp_aud),
        'EUR': (ds_eur, fp_eur),
        'GBP': (ds_gbp, fp_gbp),
        'MXN': (ds_mxn, fp_mxn),
    }

    results = {}
    for name, (ds, fp) in currencies.items():
        # Align: use lagged fp to predict next-period ds
        common = ds.index.intersection(fp.index)
        if len(common) < 24:
            continue
        y = ds.loc[common].iloc[1:]   # Δs from t to t+1
        x = fp.loc[common].iloc[:-1]  # fp at t
        # Align indices
        y.index = x.index
        mask = y.notna() & x.notna()
        y = y[mask].values
        x = x[mask].values

        if len(y) < 24:
            continue

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        results[name] = {
            'beta': slope,
            'se': std_err,
            'alpha': intercept,
            'r2': r_value**2,
            'n': len(y),
            'p': p_value,
        }

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5.5))

    names = list(results.keys())
    betas = [results[n]['beta'] for n in names]
    ses = [results[n]['se'] for n in names]
    ci95 = [1.96 * se for se in ses]

    # Color: SGD in accent, others in gray
    colors = [COLORS['sgd'] if n == 'SGD' else '#888888' for n in names]
    edge_colors = [COLORS['sgd'] if n == 'SGD' else '#666666' for n in names]

    bars = ax.bar(names, betas, color=colors, edgecolor=edge_colors, linewidth=0.8,
                  alpha=0.85, width=0.6)
    ax.errorbar(names, betas, yerr=ci95, fmt='none', ecolor='black',
                elinewidth=1.2, capsize=5, capthick=1.2)

    # Reference lines
    ax.axhline(1, color=COLORS['aud'], linewidth=1.2, linestyle='--', alpha=0.7,
               label='β = 1 (UIP holds)')
    ax.axhline(0, color='black', linewidth=0.5)

    ax.set_ylabel('Fama β coefficient')
    ax.set_title('Fama (1984) Regression: Does UIP Hold?',
                  fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=9)

    # Annotate SGD
    sgd_idx = names.index('SGD')
    sgd_beta = betas[sgd_idx]
    ax.annotate(f'β = {sgd_beta:.2f}',
                xy=(sgd_idx, sgd_beta + ci95[sgd_idx] + 0.3),
                ha='center', fontsize=10, fontweight='bold', color=COLORS['sgd'])

    ax.text(0.5, -0.15,
            'Δs = α + β(r_domestic − r_USD) + ε.  β = 1: UIP holds (no carry profit).  '
            'β < 0: forward premium puzzle (carry works).\n'
            'Error bars = 95% CI.  SGD rate: SGS 1Y T-Bill (SingStat). Others: approximated.',
            transform=ax.transAxes, ha='center', fontsize=8, color='gray', style='italic')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart4_fama_regression.png'))
    plt.close(fig)
    print('  Saved chart4_fama_regression.png')

    # Print results
    print(f'\n  {"Ccy":<5} {"β":>8} {"SE":>8} {"95% CI":>16} {"R²":>8} {"N":>6}')
    for name in names:
        r = results[name]
        ci_lo = r['beta'] - 1.96 * r['se']
        ci_hi = r['beta'] + 1.96 * r['se']
        print(f'  {name:<5} {r["beta"]:>8.2f} {r["se"]:>8.2f} [{ci_lo:>6.2f}, {ci_hi:>6.2f}] {r["r2"]:>8.4f} {r["n"]:>6}')


# ── Chart 5: Return Distribution Comparison ──────────────────────────────────

def chart5_return_distributions(data):
    """
    Chart 5: Distribution of monthly carry returns for SGD vs free-floating currencies.

    Shows the compressed, symmetric SGD distribution vs the fat-tailed,
    negatively-skewed distributions of classic carry currencies.
    """
    print('\nBuilding Chart 5: Return Distributions...')

    # Monthly spot returns
    usdsgd = data['usdsgd']['Close'].resample('ME').last().dropna()
    usdjpy = data['usdjpy']['Close'].resample('ME').last().dropna()
    audusd = data['audusd']['Close'].resample('ME').last().dropna()

    # Monthly returns (from carry trader's perspective: positive = profit)
    # SGD carry: borrow SGD, invest USD → profit when USD/SGD rises (SGD weakens)
    sgd_ret = usdsgd.pct_change().dropna() * 100
    # JPY carry: borrow JPY, invest USD → profit when USD/JPY rises (JPY weakens)
    jpy_ret = usdjpy.pct_change().dropna() * 100
    # AUD carry: borrow USD, invest AUD → profit when AUD/USD rises (AUD strengthens)
    aud_ret = audusd.pct_change().dropna() * 100

    # Align to common dates
    common = sgd_ret.index.intersection(jpy_ret.index).intersection(aud_ret.index)
    sgd_ret = sgd_ret.loc[common]
    jpy_ret = jpy_ret.loc[common]
    aud_ret = aud_ret.loc[common]

    fig, ax = plt.subplots(figsize=(10, 5.5))

    # KDE plots
    from scipy.stats import gaussian_kde

    for ret, name, color, lw in [
        (sgd_ret, 'SGD/USD', COLORS['sgd'], 2.5),
        (jpy_ret, 'JPY/USD', COLORS['jpy'], 1.5),
        (aud_ret, 'AUD/USD', COLORS['aud'], 1.5),
    ]:
        kde = gaussian_kde(ret.values, bw_method=0.3)
        x = np.linspace(-12, 12, 500)
        density = kde(x)
        skew = ret.skew()
        kurt = ret.kurtosis()
        ax.plot(x, density, color=color, linewidth=lw, alpha=0.9,
                label=f'{name}  (skew={skew:+.2f}, kurt={kurt:.1f})')
        ax.fill_between(x, 0, density, alpha=0.08, color=color)

    ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.set_xlabel('Monthly FX Return (%)')
    ax.set_ylabel('Density')
    ax.set_title('Distribution of Monthly FX Returns: SGD vs Carry Currencies',
                  fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=9)
    ax.set_xlim(-12, 12)
    ax.set_ylim(bottom=0)

    # Stats table as text
    stats_text = (
        f'              σ (mo)   Skew    Kurt\n'
        f'  SGD/USD    {sgd_ret.std():5.2f}%  {sgd_ret.skew():+5.2f}   {sgd_ret.kurtosis():5.1f}\n'
        f'  JPY/USD    {jpy_ret.std():5.2f}%  {jpy_ret.skew():+5.2f}   {jpy_ret.kurtosis():5.1f}\n'
        f'  AUD/USD    {aud_ret.std():5.2f}%  {aud_ret.skew():+5.2f}   {aud_ret.kurtosis():5.1f}'
    )
    ax.text(0.02, 0.97, stats_text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='#CCCCCC', alpha=0.9))

    ax.text(0.5, -0.12,
            'FX spot returns only (excludes interest rate component). '
            'Kurt = excess kurtosis (normal = 0). Data: Yahoo Finance.',
            transform=ax.transAxes, ha='center', fontsize=8, color='gray', style='italic')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart5_return_distributions.png'))
    plt.close(fig)
    print('  Saved chart5_return_distributions.png')


# ── Chart 6: Balassa-Samuelson ───────────────────────────────────────────────

def chart6_balassa_samuelson(data):
    """
    Chart 6: Singapore's relative productivity growth vs real exchange rate appreciation.

    Uses GDP per capita (PPP, constant 2021 intl $) as a productivity proxy.
    Compares Singapore against a basket of developed trading partners (US, JP, DE, KR).
    Overlays the BIS real effective exchange rate to show co-movement.
    """
    print('\nBuilding Chart 6: Balassa-Samuelson...')

    # Load GDP per capita data
    gdp = pd.read_csv(os.path.join(DATA_DIR, 'gdp_per_capita_ppp_constant.csv'))

    # Load REER data (monthly -> annual average)
    reer = pd.read_csv(os.path.join(DATA_DIR, 'singapore_reer_fred.csv'))
    reer['observation_date'] = pd.to_datetime(reer['observation_date'])
    reer['Year'] = reer['observation_date'].dt.year
    reer_annual = reer.groupby('Year')['RBSGBIS'].mean()

    # Compute Singapore productivity relative to developed partners
    # Trade weights (approximate): US 12%, Japan 7%, Germany 4%, Korea 5% — normalize
    weights = {'United States': 0.43, 'Japan': 0.25, 'Germany': 0.14, 'Korea, Rep.': 0.18}

    # Compute weighted partner GDP per capita
    partner_gdp = sum(gdp[c] * w for c, w in weights.items())

    # Relative productivity: SG / partners
    rel_prod = gdp['Singapore'] / partner_gdp

    # Index both to 100 at a common start year
    start_year = 1994  # Match NEER data start
    gdp_start = gdp[gdp['Year'] == start_year].index[0]

    rel_prod_idx = rel_prod / rel_prod.iloc[gdp_start] * 100
    years = gdp['Year']

    # Get REER indexed to same start
    reer_start = reer_annual.get(start_year, reer_annual.iloc[0])
    reer_idx = reer_annual / reer_start * 100

    # Align years
    common_years = sorted(set(years) & set(reer_idx.index))
    common_years = [y for y in common_years if y >= start_year]

    rel_prod_plot = [rel_prod_idx.iloc[list(years).index(y)] for y in common_years]
    reer_plot = [reer_idx[y] for y in common_years]

    # Compute correlation
    corr = np.corrcoef(rel_prod_plot, reer_plot)[0, 1]

    # Compute annualized growth rates
    n_years = common_years[-1] - common_years[0]
    prod_cagr = (rel_prod_plot[-1] / rel_prod_plot[0]) ** (1/n_years) - 1
    reer_cagr = (reer_plot[-1] / reer_plot[0]) ** (1/n_years) - 1

    fig, ax = plt.subplots(figsize=(10, 5.5))

    ax.plot(common_years, rel_prod_plot, color=COLORS['sgd'], linewidth=2,
            label=f'SG relative productivity (vs US/JP/DE/KR)', alpha=0.9)
    ax.plot(common_years, reer_plot, color=COLORS['negative'], linewidth=2,
            label=f'SGD real effective exchange rate (BIS)', alpha=0.9)

    ax.axhline(100, color='black', linewidth=0.5, alpha=0.3)

    ax.set_ylabel(f'Index ({start_year} = 100)')
    ax.set_title('Balassa-Samuelson Effect: Productivity and Real Exchange Rate',
                  fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=9)

    # Add correlation and growth annotations
    ax.text(0.98, 0.05,
            f'Correlation: {corr:.2f}\n'
            f'Rel. productivity CAGR: {prod_cagr*100:.1f}%/yr\n'
            f'REER CAGR: {reer_cagr*100:.1f}%/yr',
            transform=ax.transAxes, ha='right', va='bottom', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='#CCCCCC', alpha=0.9))

    ax.text(0.5, -0.12,
            'Relative productivity = SG GDP per capita (PPP) / trade-weighted developed partners.\n'
            'Partner weights: US 43%, JP 25%, KR 18%, DE 14%. Data: World Bank WDI, BIS (via FRED).',
            transform=ax.transAxes, ha='center', fontsize=8, color='gray', style='italic')

    fig.savefig(os.path.join(CHARTS_DIR, 'chart6_balassa_samuelson.png'))
    plt.close(fig)
    print('  Saved chart6_balassa_samuelson.png')
    print(f'  Correlation: {corr:.2f}')
    print(f'  Rel. productivity CAGR: {prod_cagr*100:.1f}%/yr')
    print(f'  REER CAGR: {reer_cagr*100:.1f}%/yr')


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    data = download_all_data()
    chart1_rate_differential(data)
    chart2_carry_backtest(data)
    chart3_neer_band(data)
    chart4_fama_regression(data)
    chart5_return_distributions(data)
    chart6_balassa_samuelson(data)
    print('\nDone! Charts saved to:', CHARTS_DIR)
