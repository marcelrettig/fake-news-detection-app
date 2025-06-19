import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const [csvFile, setCsvFile] = useState(null);
  const [useExternalInfo, setUseExternalInfo] = useState(true);
  const [promptVariant, setPromptVariant] = useState('default');
  const [outputType, setOutputType] = useState('score');
  const [iterations, setIterations] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // New: saved runs
  const [savedRuns, setSavedRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loadingSaved, setLoadingSaved] = useState(false);

  const navigate = useNavigate();

  // fetch saved benchmarks on mount
  useEffect(() => {
    fetch('http://localhost:8000/benchmarks')
      .then(res => res.json())
      .then(data => setSavedRuns(data))
      .catch(err => console.error('Failed to load saved benchmarks', err));
  }, []);

  const toBinaryLabel = v => (v ? 'True' : 'False');

  const handleFileChange = e => {
    setCsvFile(e.target.files?.[0] || null);
  };

  const handleSubmit = async e => {
    e.preventDefault();
    if (!csvFile) return;
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
        body: formData,
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error:', error);
      setResult({ error: 'An error occurred during benchmarking.' });
    } finally {
      setLoading(false);
    }
  };

  // New: load saved benchmark
  const handleLoadSaved = async () => {
    if (!selectedRunId) return;
    setLoadingSaved(true);
    try {
      const res = await fetch(`http://localhost:8000/benchmark/${selectedRunId}`);
      const data = await res.json();
      // navigate to Metrics page
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
                const corrects = Array.isArray(r.correctness)
                  ? r.correctness
                  : [];

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

  return (
    <Container maxWidth="sm">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Fake‐News Classifier
        </Typography>

        {/* New: Load saved benchmarks */}
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
                    // run.timestamp is already a string or number
                    ? new Date(run.timestamp).toLocaleString()
                    : run.id}
                    {' '} (ID: {run.id})
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

        <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
          <form onSubmit={handleSubmit}>
            {/* existing CSV upload & controls */}
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
              disabled={loading || !csvFile}
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
