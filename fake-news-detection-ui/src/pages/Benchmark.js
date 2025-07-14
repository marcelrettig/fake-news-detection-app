import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../firebase';
import { onAuthStateChanged } from 'firebase/auth';
import {
  Container,
  Box,
  Typography,
  Paper,
  Button,
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

export default function Benchmark() {
  // form state
  const [csvFile, setCsvFile] = useState(null);
  const [useExternalInfo, setUseExternalInfo] = useState(true);
  const [promptVariant, setPromptVariant] = useState('default');
  const [outputType, setOutputType] = useState('score');
  const [iterations, setIterations] = useState(1);
  const [model, setModel] = useState(process.env.REACT_APP_LLM_MODEL || 'gpt-4o');

  // auth state
  const [token, setToken] = useState('');
  const [authChecked, setAuthChecked] = useState(false);

  // job & polling state
  const [jobId, setJobId] = useState(null);
  const [polling, setPolling] = useState(false);
  const [result, setResult] = useState(null);
  const pollRef = useRef(null);

  // plot images state
  const [plotImages, setPlotImages] = useState({ roc_curve: '', pr_auc_curve: '' });
  const [loadingPlots, setLoadingPlots] = useState(false);
  const [plotError, setPlotError] = useState(null);

  // saved runs state
  const [savedRuns, setSavedRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loadingSaved, setLoadingSaved] = useState(false);

  const navigate = useNavigate();
  const API_BASE = process.env.REACT_APP_API_BASE_URL || '';

  // listen for Firebase auth state
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async user => {
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

  // fetch saved benchmarks
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/benchmarks`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(res.statusText);
        setSavedRuns(await res.json());
      } catch (err) {
        console.error('Failed to load saved benchmarks', err);
      }
    })();
  }, [token, API_BASE]);

  // poll for job results
  useEffect(() => {
    if (!jobId) return;
    setPolling(true);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/benchmark/${jobId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.accuracy !== undefined) {
            clearInterval(pollRef.current);
            setResult(data);
            setPolling(false);
            setJobId(null);
          }
        } else if (res.status !== 404) {
          clearInterval(pollRef.current);
          setPolling(false);
          setResult({ error: `Error ${res.status}: ${res.statusText}` });
          setJobId(null);
        }
      } catch (err) {
        console.error('Polling error', err);
        clearInterval(pollRef.current);
        setPolling(false);
        setJobId(null);
      }
    }, 3000);
    return () => clearInterval(pollRef.current);
  }, [jobId, token, API_BASE]);

  // fetch plots when we have a completed result
  useEffect(() => {
    if (!result?.id) return;
    setLoadingPlots(true);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/benchmark/${result.id}/plots`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(res.statusText);
        setPlotImages(await res.json());
      } catch (err) {
        console.error('Failed to load plot images', err);
        setPlotError(err);
      } finally {
        setLoadingPlots(false);
      }
    })();
  }, [result?.id, token, API_BASE]);

  const toBinaryLabel = v => (v ? 'True' : 'False');
  const handleFileChange = e => setCsvFile(e.target.files?.[0] || null);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!csvFile || !token) return;
    setResult(null);
    setJobId(null);
    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('use_external_info', String(useExternalInfo));
    formData.append('prompt_variant', promptVariant);
    formData.append('output_type', outputType);
    formData.append('iterations', String(iterations));
    formData.append('model', model);

    try {
      const res = await fetch(`${API_BASE}/benchmark`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      if (!res.ok) throw new Error(res.statusText);
      const { job_id } = await res.json();
      setJobId(job_id);
    } catch (err) {
      console.error('Error starting benchmark', err);
      setResult({ error: 'Failed to start benchmark.' });
    }
  };

  const handleLoadSaved = async () => {
    if (!selectedRunId || !token) return;
    setLoadingSaved(true);
    try {
      const res = await fetch(`${API_BASE}/benchmark/${selectedRunId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error('Failed to load saved benchmark', err);
    } finally {
      setLoadingSaved(false);
    }
  };

  const renderResults = () => {
    if (polling) {
      return (
        <Box textAlign="center" mt={4}>
          <CircularProgress />
          <Typography>Benchmark is running… (job {jobId})</Typography>
        </Box>
      );
    }
    if (!result) return null;
    if (result.error) {
      return <Typography color="error" align="center">{result.error}</Typography>;
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
            <Typography variant="subtitle2" gutterBottom>Per-Statement Results</Typography>
            <List dense>
              {result.results.map((r, idx) => (
                <ListItem key={idx} alignItems="flex-start">
                  <ListItemText
                    primary={<Typography variant="body2"><strong>#{idx+1}:</strong> {r.statement}</Typography>}
                    secondary={
                      <Box component="div" sx={{ whiteSpace: 'pre-wrap' }}>
                        <Typography variant="body2">Truth: <strong>{toBinaryLabel(r.gold_binary)}</strong></Typography>
                        {r.predictions.map((p,i) => (
                          <Typography key={i} variant="body2">
                            Iteration {i+1}: <strong>{toBinaryLabel(p)}</strong> {r.correctness[i] ? '✅' : '❌'}
                          </Typography>
                        ))}
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>

            <Box textAlign="center" mt={2}>
              <Button
                variant="contained"
                color="secondary"
                onClick={() => navigate('/metrics', {
                  state: {
                    metrics: result,
                    plotImages,
                    loadingPlots,
                    plotError
                  }
                })}
              >
                View Detailed Metrics
              </Button>
            </Box>
          </>
        )}
      </>
    );
  };

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

  if (!token) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <Typography color="error">You must be signed in to access this page.</Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Fake-News Classifier
        </Typography>

        {/* Load saved benchmarks */}
        <Paper elevation={1} sx={{ p:2, mb:4 }}>
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
                      : run.id
                    } (ID: {run.id})
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

            {/* push the Compare button to the far right */}
            <Box sx={{ flexGrow: 1 }} />

            <Button
              variant="text"
              onClick={() => navigate('/metrics/compare')}
            >
              Compare Benchmarks
            </Button>
          </Box>
        </Paper>

        {/* Benchmark form */}
        <Paper elevation={3} sx={{ p:3, mb:4 }}>
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
                control={<Switch checked={useExternalInfo} onChange={e => setUseExternalInfo(e.target.checked)} />}
                label="Use External Info"
              />
              <FormControl sx={{ minWidth:140 }} size="small">
                <InputLabel>Prompt Variant</InputLabel>
                <Select value={promptVariant} label="Prompt Variant" onChange={e => setPromptVariant(e.target.value)}>
                  <MenuItem value="default">Default</MenuItem>
                  <MenuItem value="short">Short</MenuItem>
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth:140 }} size="small">
                <InputLabel>Output Type</InputLabel>
                <Select value={outputType} label="Output Type" onChange={e => setOutputType(e.target.value)}>
                  <MenuItem value="score">Score</MenuItem>
                  <MenuItem value="binary">Binary</MenuItem>
                  <MenuItem value="detailed">Detailed</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label="Iterations"
                type="number"
                InputProps={{ inputProps: { min:1 } }}
                value={iterations}
                onChange={e => setIterations(Math.max(1, parseInt(e.target.value,10)||1))}
                size="small"
                sx={{ width:100 }}
              />
              <FormControl sx={{ minWidth:180 }} size="small">
                <InputLabel id="model-select-label">Model</InputLabel>
                <Select
                  labelId="model-select-label"
                  value={model}
                  label="Model"
                  onChange={e => setModel(e.target.value)}
                >
                  <MenuItem value="gpt-4o">GPT-4o</MenuItem>
                  <MenuItem value="gpt-4">GPT-4</MenuItem>
                  <MenuItem value="gpt-3.5-turbo">GPT-3.5 Turbo</MenuItem>
                </Select>
              </FormControl>
            </Box>
            <Button type="submit" variant="contained" color="primary" disabled={polling} fullWidth>
              {polling ? 'Benchmarking…' : 'Run Benchmark'}
            </Button>
          </form>
        </Paper>

        {renderResults()}
      </Box>
    </Container>
  );
}
