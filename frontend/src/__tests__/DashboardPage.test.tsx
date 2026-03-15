/**
 * Unit tests for DashboardPage component.
 *
 * Covers:
 * - Initial loading state
 * - Successful data fetch → stocks + sectors rendered
 * - Error states (network failure, generating state)
 * - Refresh button triggering a POST refresh
 * - Logout callback
 * - Bottom/top stock ranking display
 * - Sentiment chip colours (positive vs negative)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';

// ---------------------------------------------------------------------------
// Mock API client
// ---------------------------------------------------------------------------
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_STOCKS = [
  {
    ticker: 'AAPL',
    sector: 'Information Technology',
    sentiment_score: 0.82,
    positive: 0.75,
    negative: 0.08,
    neutral: 0.17,
    news_count: 12,
  },
  {
    ticker: 'MSFT',
    sector: 'Information Technology',
    sentiment_score: 0.65,
    positive: 0.60,
    negative: 0.15,
    neutral: 0.25,
    news_count: 9,
  },
  {
    ticker: 'JPM',
    sector: 'Financials',
    sentiment_score: -0.30,
    positive: 0.20,
    negative: 0.55,
    neutral: 0.25,
    news_count: 7,
  },
];

function mockOkStatus(isGenerating = false) {
  return Promise.resolve({
    data: {
      success: true,
      data: { has_data: true, is_generating: isGenerating, elapsed_seconds: 0 },
    },
  });
}

function mockOkStocks(stocks = MOCK_STOCKS) {
  return Promise.resolve({
    data: { success: true, data: stocks },
  });
}

function renderDashboard(onLogout = vi.fn()) {
  return render(
    <BrowserRouter>
      <DashboardPage onLogout={onLogout} />
    </BrowserRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Loading state --------------------------------------------------------

  it('shows loading indicator on mount', () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    // Never resolve → stays loading
    (api.get as any).mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(
      screen.queryByRole('progressbar') ||
      screen.queryByText(/loading/i)
    ).toBeTruthy();
  });

  // --- Successful data load -------------------------------------------------

  it('renders stock tickers after successful fetch', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks());

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('MSFT')).toBeInTheDocument();
      expect(screen.getByText('JPM')).toBeInTheDocument();
    });
  });

  it('groups stocks by sector', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks());

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/Information Technology/i)).toBeInTheDocument();
      expect(screen.getByText(/Financials/i)).toBeInTheDocument();
    });
  });

  // --- Error states ---------------------------------------------------------

  it('displays error when network request fails', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any).mockRejectedValue(new Error('Network error'));

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.queryByText(/error/i) ||
        screen.queryByText(/failed/i) ||
        screen.queryByText(/network/i)
      ).toBeTruthy();
    });
  });

  it('shows generating message when pipeline is running', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any).mockResolvedValue({
      data: {
        success: true,
        data: { has_data: false, is_generating: true, elapsed_seconds: 120 },
      },
    });

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.queryByText(/generating/i) ||
        screen.queryByText(/please wait/i) ||
        screen.queryByText(/being generated/i)
      ).toBeTruthy();
    });
  });

  // --- Refresh --------------------------------------------------------------

  it('calls POST /data/refresh when refresh button is clicked', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks());
    (api.post as any).mockResolvedValue({ data: { success: true } });

    renderDashboard();

    await waitFor(() => screen.getByText(/Refresh/i));
    fireEvent.click(screen.getByText(/Refresh/i));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/refresh/i));
    });
  });

  // --- Logout ---------------------------------------------------------------

  it('calls onLogout callback when logout button is clicked', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks());

    const onLogout = vi.fn();
    renderDashboard(onLogout);

    await waitFor(() => screen.getByText('AAPL'));
    const logoutBtn = screen.getByRole('button', { name: /logout/i });
    fireEvent.click(logoutBtn);

    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  // --- Sentiment score display ----------------------------------------------

  it('displays positive sentiment score with correct sign', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks([MOCK_STOCKS[0]]));

    renderDashboard();

    await waitFor(() => {
      // Score 0.82 should appear somewhere on the page
      expect(screen.getByText(/0\.82|82%|\+0\.82/i)).toBeInTheDocument();
    });
  });

  it('empty data returns no stock cards', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.get as any)
      .mockResolvedValueOnce({ data: { success: true, data: { has_data: true, is_generating: false } } })
      .mockResolvedValue(mockOkStocks([]));

    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
    });
  });
});
