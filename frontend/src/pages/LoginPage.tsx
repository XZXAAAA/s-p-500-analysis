import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Container,
  Paper,
  TextField,
  Button,
  Alert,
  Box,
  Typography,
  Stack,
} from '@mui/material'
import apiClient from '../api/client'

interface LoginPageProps {
  onLogin: (token: string) => void
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const extractErrorMessage = (err: any) => {
    // Check detail field first (FastAPI standard error format)
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string') {
      return detail
    }
    
    // Handle Pydantic validation errors (array format)
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item?.msg ?? item?.message ?? '')
        .filter(Boolean)
      return messages.length > 0 ? messages.join('; ') : 'Login failed'
    }
    
    // Check message field
    if (err?.response?.data?.message) {
      return err.response.data.message
    }
    
    // Return default message based on status code
    if (err?.response?.status === 401) {
      return 'Incorrect username or password'
    }
    if (err?.response?.status === 500) {
      return 'Server error, please try again later'
    }
    
    return 'Login failed, please check your credentials'
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await apiClient.post('/auth/login', {
        username,
        password,
      })

      if (response.data.success) {
        const token = response.data.data.token
        onLogin(token)
        navigate('/dashboard')
      } else {
        setError(response.data.message || 'Login failed')
        setLoading(false)
      }
    } catch (err: any) {
      console.error('Login error:', err)
      setError(extractErrorMessage(err))
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        background:
          'linear-gradient(135deg, rgba(25,118,210,0.15), rgba(220,0,78,0.15))',
        py: 6,
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={6}
          sx={{
            p: 5,
            borderRadius: 4,
            backdropFilter: 'blur(6px)',
          }}
        >
          <Stack spacing={3}>
            <Box textAlign="center">
              <Typography variant="h4" fontWeight={600}>
                Welcome back
              </Typography>
              <Typography variant="body2" color="text.secondary" mt={1}>
                Sign in to explore the S&amp;P 500 sentiment dashboard
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" sx={{ borderRadius: 2 }}>
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <Stack spacing={2}>
                <TextField
                  fullWidth
                  label="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />

                <TextField
                  fullWidth
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                <Button
                  fullWidth
                  size="large"
                  variant="contained"
                  color="primary"
                  type="submit"
                  sx={{ mt: 1, textTransform: 'none', fontSize: '1rem' }}
                  disabled={loading}
                >
                  {loading ? 'Signing in...' : 'Sign in'}
                </Button>
              </Stack>
            </form>

            <Typography align="center">
              Need an account? <Link to="/register">Create one</Link>
            </Typography>
          </Stack>
        </Paper>
      </Container>
    </Box>
  )
}

export default LoginPage

