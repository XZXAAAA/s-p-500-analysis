/**
 * Unit tests for RegisterPage component.
 *
 * Covers:
 * - Form rendering (all four fields + submit button)
 * - Input change handling
 * - Password mismatch validation
 * - Loading state during POST
 * - Successful registration → navigate to /dashboard
 * - API error → error message displayed
 * - Link back to login page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import RegisterPage from '../pages/RegisterPage';

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

function renderRegister() {
  return render(
    <BrowserRouter>
      <RegisterPage />
    </BrowserRouter>
  );
}

function fillForm(
  username: string,
  email: string,
  password: string,
  confirm: string
) {
  fireEvent.change(screen.getByLabelText(/username/i), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  const pwFields = screen.getAllByLabelText(/password/i);
  fireEvent.change(pwFields[0], { target: { value: password } });
  fireEvent.change(pwFields[1], { target: { value: confirm } });
  fireEvent.click(screen.getByRole('button', { name: /register|sign up/i }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // --- Rendering -----------------------------------------------------------

  it('renders Sign Up / Register heading', () => {
    renderRegister();
    expect(
      screen.queryByText(/sign up/i) || screen.queryByText(/register/i)
    ).toBeTruthy();
  });

  it('renders username, email and password fields', () => {
    renderRegister();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/password/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders a register/sign-up submit button', () => {
    renderRegister();
    expect(
      screen.getByRole('button', { name: /register|sign up/i })
    ).toBeInTheDocument();
  });

  it('has a link back to the login page', () => {
    renderRegister();
    const link = (
      screen.queryByText(/already have an account/i) ||
      screen.queryByText(/sign in/i) ||
      screen.queryByText(/back to login/i)
    );
    expect(link).toBeTruthy();
  });

  // --- Input handling -------------------------------------------------------

  it('updates username field on input', () => {
    renderRegister();
    const input = screen.getByLabelText(/username/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'bob' } });
    expect(input.value).toBe('bob');
  });

  it('updates email field on input', () => {
    renderRegister();
    const input = screen.getByLabelText(/email/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'bob@example.com' } });
    expect(input.value).toBe('bob@example.com');
  });

  // --- Validation -----------------------------------------------------------

  it('does not submit with empty fields', async () => {
    renderRegister();
    fireEvent.click(screen.getByRole('button', { name: /register|sign up/i }));
    await waitFor(() => {
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  it('shows error when passwords do not match', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    renderRegister();
    fillForm('bob', 'bob@example.com', 'Pass1!', 'Different1!');
    await waitFor(() => {
      expect(
        screen.queryByText(/match/i) ||
        screen.queryByText(/mismatch/i) ||
        screen.queryByText(/do not match/i)
      ).toBeTruthy();
      expect(api.post).not.toHaveBeenCalled();
    });
  });

  // --- Loading state --------------------------------------------------------

  it('disables button while request is in-flight', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockImplementation(() => new Promise(() => {}));
    renderRegister();
    fillForm('bob', 'bob@example.com', 'P@ssword1', 'P@ssword1');
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /register|sign up|registering/i })
      ).toBeDisabled();
    });
  });

  // --- Successful registration ----------------------------------------------

  it('navigates to /dashboard on success', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: {
        success: true,
        data: { token: 'jwt-xyz', user: { id: 2, username: 'bob' } },
      },
    });

    renderRegister();
    fillForm('bob', 'bob@example.com', 'P@ssword1', 'P@ssword1');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('saves token to localStorage on success', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: {
        success: true,
        data: { token: 'jwt-xyz', user: { id: 2, username: 'bob' } },
      },
    });

    renderRegister();
    fillForm('bob', 'bob@example.com', 'P@ssword1', 'P@ssword1');

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('jwt-xyz');
    });
  });

  // --- Failed registration --------------------------------------------------

  it('displays error returned by the API', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockResolvedValue({
      data: { success: false, message: 'Username already exists' },
    });

    renderRegister();
    fillForm('bob', 'bob@example.com', 'P@ssword1', 'P@ssword1');

    await waitFor(() => {
      expect(
        screen.queryByText(/already exists/i) ||
        screen.queryByText(/error/i) ||
        screen.queryByText(/failed/i)
      ).toBeTruthy();
    });
  });

  it('displays error on network failure', async () => {
    const { default: api } = vi.mocked(await import('../api/client'));
    (api.post as any).mockRejectedValue(new Error('Network Error'));

    renderRegister();
    fillForm('bob', 'bob@example.com', 'P@ssword1', 'P@ssword1');

    await waitFor(() => {
      expect(
        screen.queryByText(/error/i) || screen.queryByText(/failed/i)
      ).toBeTruthy();
    });
  });
});
