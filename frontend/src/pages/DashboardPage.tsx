import React, { useState, useEffect } from 'react'
import {
  Container,
  Box,
  Button,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Chip,
  LinearProgress,
  Alert,
  Stack,
  IconButton,
  Tooltip,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import LogoutIcon from '@mui/icons-material/Logout'
import apiClient from '../api/client'

interface DashboardPageProps {
  onLogout: () => void
}

interface StockData {
  ticker: string
  sector: string
  sentiment_score: number
  positive: number
  negative: number
  neutral: number
  timestamp?: number
}

const DashboardPage: React.FC<DashboardPageProps> = ({ onLogout }) => {
  const [topStocks, setTopStocks] = useState<StockData[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadTopStocks()
  }, [])

  const loadTopStocks = async () => {
    try {
      setLoading(true)
      setError('')
      
      // First check if data is still being generated
      const statusResponse = await apiClient.get('/data/status')
      if (statusResponse.data.data?.is_generating) {
        const elapsed = statusResponse.data.data.elapsed_seconds || 0
        setError(`Data is being generated... (${Math.floor(elapsed / 60)} min ${elapsed % 60} sec elapsed). Please wait or refresh in a few minutes.`)
        setLoading(false)
        return
      }
      
      // Load all stocks (limit=500 to get all S&P 500)
      const response = await apiClient.get('/data/top-stocks?limit=500')
      if (response.data.success) {
        const stocks = response.data.data || []
        if (stocks.length === 0) {
          setError('No data available yet. Please wait for data generation to complete.')
        } else {
          setTopStocks(stocks)
          console.log(`Loaded ${stocks.length} stocks`)
        }
      } else {
        setError(response.data.message || 'Data is being generated, please wait...')
      }
    } catch (err: any) {
      console.error('Failed to load top stocks', err)
      if (err?.response?.data?.message) {
        setError(err.response.data.message)
      } else {
        setError('Failed to load stock data. Please try refreshing.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async (useReal: boolean = false) => {
    try {
      setRefreshing(true)
      setError('')
      const url = useReal ? '/data/refresh?use_real=true' : '/data/refresh'
      await apiClient.post(url)
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await apiClient.get('/data/status')
          if (statusResponse.data.success && !statusResponse.data.data.is_generating) {
            clearInterval(pollInterval)
            await loadTopStocks()
            setRefreshing(false)
          }
        } catch (err) {
          console.error('Failed to check status', err)
        }
      }, 2000)
      
      // Timeout after 15 minutes
      setTimeout(() => {
        clearInterval(pollInterval)
        setRefreshing(false)
      }, 900000)
    } catch (err) {
      console.error('Failed to refresh data', err)
      setError('Failed to refresh data. Please try again.')
      setRefreshing(false)
    }
  }

  const getSentimentColor = (score: number) => {
    if (score > 0.3) return '#4caf50' // Green
    if (score > 0) return '#8bc34a' // Light green
    if (score > -0.3) return '#ff9800' // Orange
    return '#f44336' // Red
  }

  const getSentimentLabel = (score: number) => {
    if (score > 0.5) return 'Very Positive'
    if (score > 0.2) return 'Positive'
    if (score > -0.2) return 'Neutral'
    if (score > -0.5) return 'Negative'
    return 'Very Negative'
  }

  // Group stocks by sector
  const groupBySector = (stocks: StockData[]) => {
    const grouped: { [key: string]: StockData[] } = {}
    stocks.forEach((stock) => {
      if (!grouped[stock.sector]) {
        grouped[stock.sector] = []
      }
      grouped[stock.sector].push(stock)
    })
    return grouped
  }

  const stocksBySector = groupBySector(topStocks)
  const sectors = Object.keys(stocksBySector).sort()

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, rgba(25,118,210,0.05), rgba(156,39,176,0.05))',
        py: 4,
      }}
    >
      <Container maxWidth="xl">
        {/* Header */}
        <Paper
          elevation={2}
          sx={{
            p: 3,
            mb: 4,
            borderRadius: 3,
            background: 'linear-gradient(135deg, #1976d2 0%, #9c27b0 100%)',
            color: 'white',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              <Typography variant="h4" fontWeight={600} gutterBottom>
                S&P 500 Sentiment Dashboard
              </Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>
                Real-time sentiment analysis powered by news data and VADER
              </Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Tooltip title="Refresh data from cache (instant)">
                <Button
                  variant="contained"
                  onClick={() => loadTopStocks()}
                  disabled={refreshing}
                  startIcon={<RefreshIcon />}
                  sx={{
                    bgcolor: 'rgba(255,255,255,0.2)',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.3)' },
                  }}
                >
                  {refreshing ? 'Refreshing...' : 'Refresh View'}
                </Button>
              </Tooltip>
              <Tooltip title="Re-analyze all stocks with latest news (5-10 min)">
                <Button
                  variant="contained"
                  onClick={() => handleRefresh(true)}
                  disabled={refreshing}
                  startIcon={<TrendingUpIcon />}
                  sx={{
                    bgcolor: 'rgba(255,255,255,0.2)',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.3)' },
                  }}
                >
                  Re-analyze
                </Button>
              </Tooltip>
              <Tooltip title="Logout">
                <IconButton
                  onClick={onLogout}
                  sx={{
                    color: 'white',
                    bgcolor: 'rgba(255,255,255,0.2)',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.3)' },
                  }}
                >
                  <LogoutIcon />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>
        </Paper>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {/* Loading State */}
        {loading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 10 }}>
            <CircularProgress size={60} />
            <Typography variant="h6" sx={{ mt: 3, color: 'text.secondary' }}>
              Loading sentiment data...
            </Typography>
          </Box>
        ) : (
          <>
            {/* Stats Summary */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
              <Grid item xs={12} sm={4}>
                <Paper sx={{ p: 3, borderRadius: 3, textAlign: 'center' }}>
                  <Typography variant="h3" color="success.main" fontWeight={600}>
                    {topStocks.filter((s) => s.sentiment_score > 0).length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Positive Sentiment
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Paper sx={{ p: 3, borderRadius: 3, textAlign: 'center' }}>
                  <Typography variant="h3" color="warning.main" fontWeight={600}>
                    {topStocks.filter((s) => s.sentiment_score >= -0.2 && s.sentiment_score <= 0.2).length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Neutral Sentiment
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Paper sx={{ p: 3, borderRadius: 3, textAlign: 'center' }}>
                  <Typography variant="h3" color="error.main" fontWeight={600}>
                    {topStocks.filter((s) => s.sentiment_score < 0).length}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Negative Sentiment
                  </Typography>
                </Paper>
              </Grid>
            </Grid>

            {/* Stock Cards - Grouped by Sector */}
            <Stack spacing={4}>
              {sectors.map((sector) => (
                <Box key={sector}>
                  <Paper
                    sx={{
                      p: 2,
                      mb: 2,
                      borderRadius: 2,
                      background: 'linear-gradient(135deg, rgba(25,118,210,0.1), rgba(156,39,176,0.1))',
                    }}
                  >
                    <Typography variant="h5" fontWeight={600}>
                      {sector}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {stocksBySector[sector].length} stocks
                    </Typography>
                  </Paper>

                  <Grid container spacing={3}>
                    {stocksBySector[sector].map((stock) => (
                      <Grid item xs={12} sm={6} md={4} lg={3} key={stock.ticker}>
                        <Card
                          elevation={3}
                          sx={{
                            height: '100%',
                            borderRadius: 3,
                            transition: 'transform 0.2s, box-shadow 0.2s',
                            '&:hover': {
                              transform: 'translateY(-4px)',
                              boxShadow: 6,
                            },
                            borderLeft: `4px solid ${getSentimentColor(stock.sentiment_score)}`,
                          }}
                        >
                          <CardContent>
                            {/* Ticker */}
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                              <Typography variant="h5" fontWeight={700}>
                                {stock.ticker}
                              </Typography>
                              {stock.sentiment_score > 0 ? (
                                <TrendingUpIcon sx={{ color: 'success.main', fontSize: 32 }} />
                              ) : (
                                <TrendingDownIcon sx={{ color: 'error.main', fontSize: 32 }} />
                              )}
                            </Box>

                            {/* Sentiment Score */}
                            <Box sx={{ mb: 2 }}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                <Typography variant="body2" color="text.secondary">
                                  Sentiment Score
                                </Typography>
                                <Typography
                                  variant="h6"
                                  fontWeight={600}
                                  sx={{ color: getSentimentColor(stock.sentiment_score) }}
                                >
                                  {(stock.sentiment_score * 100).toFixed(1)}%
                                </Typography>
                              </Box>
                              <LinearProgress
                                variant="determinate"
                                value={Math.abs(stock.sentiment_score) * 100}
                                sx={{
                                  height: 8,
                                  borderRadius: 4,
                                  bgcolor: 'rgba(0,0,0,0.1)',
                                  '& .MuiLinearProgress-bar': {
                                    bgcolor: getSentimentColor(stock.sentiment_score),
                                    borderRadius: 4,
                                  },
                                }}
                              />
                              <Typography
                                variant="caption"
                                sx={{
                                  display: 'block',
                                  mt: 0.5,
                                  color: getSentimentColor(stock.sentiment_score),
                                  fontWeight: 600,
                                }}
                              >
                                {getSentimentLabel(stock.sentiment_score)}
                              </Typography>
                            </Box>

                            {/* Breakdown */}
                            <Stack spacing={1}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">
                                  Positive
                                </Typography>
                                <Typography variant="caption" fontWeight={600} color="success.main">
                                  {(stock.positive * 100).toFixed(1)}%
                                </Typography>
                              </Box>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">
                                  Neutral
                                </Typography>
                                <Typography variant="caption" fontWeight={600} color="text.secondary">
                                  {(stock.neutral * 100).toFixed(1)}%
                                </Typography>
                              </Box>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">
                                  Negative
                                </Typography>
                                <Typography variant="caption" fontWeight={600} color="error.main">
                                  {(stock.negative * 100).toFixed(1)}%
                                </Typography>
                              </Box>
                            </Stack>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              ))}
            </Stack>
          </>
        )}
      </Container>
    </Box>
  )
}

export default DashboardPage

