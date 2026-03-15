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
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import apiClient from '../api/client'

interface RegisterPageProps {
  onRegister: (token: string) => void
}

const RegisterPage: React.FC<RegisterPageProps> = ({ onRegister }) => {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirm_password: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

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
      return messages.length > 0 ? messages.join('; ') : 'Registration failed'
    }
    
    // Check message field
    if (err?.response?.data?.message) {
      return err.response.data.message
    }
    
    // Return default message based on status code
    if (err?.response?.status === 409) {
      return 'Username or email already exists'
    }
    if (err?.response?.status === 400) {
      return 'Invalid input, please check your information'
    }
    if (err?.response?.status === 500) {
      return 'Server error, please try again later'
    }
    
    return 'Registration failed, please try again'
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const response = await apiClient.post('/auth/register', formData)

      if (response.data.success) {
        const token = response.data.data.token
        setSuccess('Registration successful! Redirecting...')
        onRegister(token)
        setTimeout(() => {
          navigate('/dashboard')
        }, 1000)
      } else {
        setError(response.data.message || 'Registration failed')
        setLoading(false)
      }
    } catch (err: any) {
      console.error('Registration error:', err)
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
          'linear-gradient(135deg, rgba(25,118,210,0.12), rgba(0,200,166,0.15))',
        py: 6,
      }}
    >
      <Container maxWidth="md">
        <Paper
          elevation={6}
          sx={{
            p: { xs: 3, md: 5 },
            borderRadius: 4,
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            gap: 4,
          }}
        >
          <Box>
              <Typography variant="h4" fontWeight={600}>
                Create your account
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1} mb={3}>
                Gain instant access to the complete S&amp;P 500 sentiment analytics suite.
            </Typography>

            <List>
              {[
                'Real-time sentiment heatmaps for all S&P 500 sectors',
                'Personalized watchlists and preferences synced to your account',
                'Interactive visualizations with multi-dimensional insights',
              ].map((item) => (
                <ListItem key={item} disableGutters>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <CheckCircleIcon color="primary" fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary={item} />
                </ListItem>
              ))}
            </List>

            <Typography variant="subtitle2" color="text.secondary" mt={2}>
              Password policy: minimum 8 characters with uppercase, lowercase, number, and special symbol.
            </Typography>
          </Box>

          <Box component="form" onSubmit={handleSubmit}>
            <Stack spacing={2}>
              {error && (
                <Alert severity="error" sx={{ borderRadius: 2 }}>
                  {error}
                </Alert>
              )}
              {success && (
                <Alert severity="success" sx={{ borderRadius: 2 }}>
                  {success}
                </Alert>
              )}

              <TextField
                fullWidth
                label="Username"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
              />

              <TextField
                fullWidth
                label="Work email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
              />

              <TextField
                fullWidth
                label="Password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
              />

              <TextField
                fullWidth
                label="Confirm password"
                name="confirm_password"
                type="password"
                value={formData.confirm_password}
                onChange={handleChange}
                required
              />

              <Button
                fullWidth
                size="large"
                variant="contained"
                color="primary"
                type="submit"
                sx={{ textTransform: 'none', fontSize: '1rem' }}
                disabled={loading}
              >
                {loading ? 'Creating account...' : 'Sign up'}
              </Button>

              <Typography align="center">
                Already have an account? <Link to="/login">Back to sign in</Link>
              </Typography>
            </Stack>
          </Box>
        </Paper>
      </Container>
    </Box>
  )
}

export default RegisterPage

