import React, { useState, useEffect } from 'react'
import {
  Container,
  Box,
  Button,
  Typography,
  CircularProgress,
} from '@mui/material'
import apiClient from '../api/client'

interface AnalyticsPageProps {
  onLogout: () => void
}

const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ onLogout }) => {
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async () => {
    try {
      setLoading(true)
      const response = await apiClient.get('/viz/sector-analysis')
      if (response.data.success) {
        setAnalyticsData(response.data.data)
      }
    } catch (err) {
      console.error('Failed to load analytics', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
        <Typography variant="h4">Analytics</Typography>
        <Button variant="outlined" color="secondary" onClick={onLogout}>
          Logout
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Sector Analysis
          </Typography>
          <pre>{JSON.stringify(analyticsData, null, 2)}</pre>
        </Box>
      )}
    </Container>
  )
}

export default AnalyticsPage

