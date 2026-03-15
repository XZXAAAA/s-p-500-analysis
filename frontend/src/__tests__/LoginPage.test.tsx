/**
 * Unit tests for LoginPage component.
 *
 * Covers:
 * - Form rendering (inputs, labels, submit button)
 * - Input change handling
 * - Validation: empty fields prevent navigation
 * - Loading state while POST is in-flight
 * - Successful login → navigates to dashboard + persists token
 * - Failed login → error message displayed
 * - Register link present and correctly routed
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...(actual as object),
    useNavigate: () => mockNavigate,
  };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLogin() {
  return render(
    <BrowserRouter>
      <LoginPage />
    </BrowserRouter>
  );
}

function fillAndSubmit(username: string, password: string) {
  fireEvent.change(screen.getByLabelText(/username/i), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: password },
  });
  fireEvent.click(screen.getByRole('button', { name: /login/i }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // --- Rendering -----------------------------------------------------------

  it('renders Sign In heading', () => {
    renderLogin();
    expect(screen.getByText(/sign in/i)).toBeInTheDocument();
  });

  it('renders username input', () => {
    renderLogin();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  });

  it('renders password input', () => {
    renderLogin();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('renders Login submit button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('has a link to the register page', () => {
    renderLogin();
    const link = screen.getByText(/don't have an account/i).closest('a');
    expect(link).toHaveAttribute('href', '/register');
  });

  // --- Input handling -------------------------------------------------------

  it('updates username value on change', () => {
    renderLogin();
    const input = screen.getByLabelText(/username/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'alice' } });
    expect(input.value).toBe('alice');
  });

  it('updates password value on change', () => {
    renderLogin();
    const input = screen.getByLabelText(/password/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'secret123' } });
    expect(input.value).toBe('secret123');
  });

  // --- Validation -----------------------------------------------------------

  it('does not navigate when submitted with empty fields', async () => {
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /login/i }));
    await waitFor(() => {
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  // --- Loading state --------------------------------------------------------

  it('disables submit button while login request is in-flight', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    renderLogin();
    fillAndSubmit('alice', 'P@ssword1');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /login|logging in/i })).toBeDisabled();
    });
  });

  // --- Successful login -----------------------------------------------------

  it('navigates to /dashboard on successful login', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: {
        success: true,
        data: { token: 'jwt-abc', user: { id: 1, username: 'alice' } },
      },
    });

    renderLogin();
    fillAndSubmit('alice', 'P@ssword1');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('persists token to localStorage on successful login', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: {
        success: true,
        data: { token: 'jwt-abc', user: { id: 1, username: 'alice' } },
      },
    });

    renderLogin();
    fillAndSubmit('alice', 'P@ssword1');

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('jwt-abc');
    });
  });

  // --- Failed login ---------------------------------------------------------

  it('shows error message on invalid credentials', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: { success: false, message: 'Invalid username or password' },
    });

    renderLogin();
    fillAndSubmit('alice', 'wrongpass');

    await waitFor(() => {
      expect(
        screen.queryByText(/invalid/i) ||
        screen.queryByText(/incorrect/i) ||
        screen.queryByText(/wrong/i) ||
        screen.queryByText(/failed/i)
      ).toBeTruthy();
    });
  });

  it('shows error message on network failure', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockRejectedValue(new Error('Network Error'));

    renderLogin();
    fillAndSubmit('alice', 'P@ssword1');

    await waitFor(() => {
      expect(
        screen.queryByText(/error/i) ||
        screen.queryByText(/failed/i) ||
        screen.queryByText(/network/i)
      ).toBeTruthy();
    });
  });

  it('does not navigate on failure', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockRejectedValue(new Error('Server down'));

    renderLogin();
    fillAndSubmit('alice', 'P@ssword1');

    await waitFor(() => {
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });
});
