import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../firebase';                   // your Firebase init
import { onAuthStateChanged } from 'firebase/auth';
import {
  Container,
  Box,
  Typography,
  Paper,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Divider,
  List,
  ListItem,
  ListItemText,
  TextField,
  CircularProgress
} from '@mui/material';

const Benchmark = () => {
  // form state
  const [csvFile, setCsvFile] = useState(null);
  const [useExternalInfo, setUseExternalInfo] = useState(true);
  const [promptVariant, setPromptVariant] = useState('default');
  const [outputType, setOutputType] = useState('score');
  const [iterations, setIterations] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // auth state
  const [token, setToken] = useState('');
  const [authChecked, setAuthChecked] = useState(false);

  // saved runs state
  const [savedRuns, setSavedRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loadingSaved, setLoadingSaved] = useState(false);

  const navigate = useNavigate();

  // listen for Firebase auth state
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        const tk = await user.getIdToken(true);
        setToken(tk);
      } else {
        setToken('');
      }
      setAuthChecked(true);
    });
    return () => unsubscribe();
  }, []);

  // fetch saved benchmarks once we have a token
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch('http://localhost:8000/benchmarks', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        setSavedRuns(data);
      } catch (err) {
        console.error('Failed to load saved benchmarks', err);
      }
    })();
  }, [token]);

  const toBinaryLabel = v => (v ? 'True' : 'False');

  const handleFileChange = e => {
    setCsvFile(e.target.files?.[0] || null);
  };

  const handleSubmit = async e => {
    e.preventDefault();
    if (!csvFile || !token) return;
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('use_external_info', useExternalInfo);
    formData.append('prompt_variant', promptVariant);
    formData.append('output_type', outputType);
    formData.append('iterations', iterations);

    try {
      const response = await fetch('http://localhost:8000/benchmark', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!response.ok) throw new Error(response.statusText);
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error:', error);
      setResult({ error: 'An error occurred during benchmarking.' });
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSaved = async () => {
    if (!selectedRunId || !token) return;
    setLoadingSaved(true);
    try {
      const res = await fetch(
        `http://localhost:8000/benchmark/${selectedRunId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      navigate('/metrics', { state: { metrics: data } });
    } catch (err) {
      console.error('Failed to load saved benchmark', err);
    } finally {
      setLoadingSaved(false);
    }
  };

  const renderResults = () => {
    if (!result) return null;
    if (result.error) {
      return (
        <Typography color="error" align="center">
          {result.error}
        </Typography>
      );
    }

    return (
      <>
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2">Overall Accuracy</Typography>
          <Typography variant="h5">
            {typeof result.accuracy === 'number'
              ? `${(result.accuracy * 100).toFixed(2)}%`
              : '–'}
          </Typography>
        </Box>
        <Divider sx={{ my: 2 }} />

        {Array.isArray(result.results) && result.results.length > 0 && (
          <>
            <Typography variant="subtitle2" gutterBottom>
              Per-Statement Results
            </Typography>
            <List dense>
              {result.results.map((r, idx) => {
                const preds = Array.isArray(r.predictions) ? r.predictions : [];
                const corrects = Array.isArray(r.correctness) ? r.correctness : [];

                return (
                  <ListItem key={idx} alignItems="flex-start">
                    <ListItemText
                      primary={
                        <Typography variant="body2">
                          <strong>#{idx + 1}:</strong> {r.statement}
                        </Typography>
                      }
                      secondary={
                        <Box component="div" sx={{ whiteSpace: 'pre-wrap' }}>
                          <Typography variant="body2">
                            Truth:{' '}
                            <strong>{toBinaryLabel(r.gold_binary)}</strong>
                          </Typography>
                          {preds.map((p, i) => (
                            <Typography key={i} variant="body2">
                              Iteration {i + 1}: <strong>{toBinaryLabel(p)}</strong>{' '}
                              {corrects[i] ? '✅' : '❌'}
                            </Typography>
                          ))}
                        </Box>
                      }
                    />
                  </ListItem>
                );
              })}
            </List>

            <Box textAlign="center" mt={2}>
              <Button
                variant="contained"
                color="secondary"
                onClick={() => navigate('/metrics', { state: { metrics: result } })}
              >
                View Detailed Metrics
              </Button>
            </Box>
          </>
        )}
      </>
    );
  };

  // if auth check not done yet
  if (!authChecked) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <CircularProgress />
          <Typography>Checking authentication…</Typography>
        </Box>
      </Container>
    );
  }

  // if not signed in
  if (!token) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <Typography color="error">
            You must be signed in to access this page.
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Fake‐News Classifier
        </Typography>

        {/* Load saved benchmarks */}
        <Paper elevation={1} sx={{ p: 2, mb: 4 }}>
          <Typography variant="subtitle1">Load Saved Benchmark</Typography>
          <Box display="flex" gap={2} alignItems="center" mt={1}>
            <FormControl fullWidth size="small">
              <InputLabel id="saved-run-label">Select Run</InputLabel>
              <Select
                labelId="saved-run-label"
                value={selectedRunId}
                label="Select Run"
                onChange={e => setSelectedRunId(e.target.value)}
              >
                {savedRuns.map(run => (
                  <MenuItem key={run.id} value={run.id}>
                    {run.timestamp
                      ? new Date(run.timestamp).toLocaleString()
                      : run.id}{' '}
                    (ID: {run.id})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              onClick={handleLoadSaved}
              disabled={!selectedRunId || loadingSaved}
            >
              {loadingSaved ? <CircularProgress size={20} /> : 'Load'}
            </Button>
          </Box>
        </Paper>

        {/* Benchmark form */}
        <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
          <form onSubmit={handleSubmit}>
            <FormControl fullWidth margin="normal">
              <input
                accept=".csv"
                id="csv-upload"
                type="file"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <label htmlFor="csv-upload">
                <Button variant="outlined" component="span" fullWidth>
                  {csvFile ? csvFile.name : 'Upload CSV of Statements'}
                </Button>
              </label>
            </FormControl>

            <Box display="flex" flexWrap="wrap" gap={2} my={2}>
              <FormControlLabel
                control={
                  <Switch
                    checked={useExternalInfo}
                    onChange={e => setUseExternalInfo(e.target.checked)}
                  />
                }
                label="Use External Info"
              />
              <FormControl sx={{ minWidth: 140 }} size="small">
                <InputLabel>Prompt Variant</InputLabel>
                <Select
                  value={promptVariant}
                  label="Prompt Variant"
                  onChange={e => setPromptVariant(e.target.value)}
                >
                  <MenuItem value="default">Default</MenuItem>
                  <MenuItem value="short">Short</MenuItem>
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 140 }} size="small">
                <InputLabel>Output Type</InputLabel>
                <Select
                  value={outputType}
                  label="Output Type"
                  onChange={e => setOutputType(e.target.value)}
                >
                  <MenuItem value="score">Score</MenuItem>
                  <MenuItem value="binary">Binary</MenuItem>
                  <MenuItem value="detailed">Detailed</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label="Iterations"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
                value={iterations}
                onChange={e =>
                  setIterations(Math.max(1, parseInt(e.target.value, 10) || 1))
                }
                size="small"
                sx={{ width: 100 }}
              />
            </Box>

            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={loading}
              fullWidth
            >
              {loading ? 'Benchmarking...' : 'Run Benchmark'}
            </Button>
          </form>
        </Paper>

        {renderResults()}
      </Box>
    </Container>
  );
};

export default Benchmark;
