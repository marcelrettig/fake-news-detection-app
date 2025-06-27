import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Container, Box, Typography, Button, Divider,
  Table, TableBody, TableCell, TableHead, TableRow, Paper
} from '@mui/material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  LineChart, Line, CartesianGrid
} from 'recharts';

const Metrics = () => {
  const { state } = useLocation();
  const navigate = useNavigate();

  const raw = state?.metrics || {};
  const data = { ...(raw.metrics ?? raw), ...(raw.params ?? {}) };

  // Compute all chart data unconditionally
  const {
    prfData,
    rocData,
    prCurveData,
    prAuc,
    histData,
    iterData
  } = useMemo(() => {
    if (!data || !Array.isArray(data.results)) {
      return {
        prfData: [], rocData: [], prCurveData: [], prAuc: 0,
        histData: [], iterData: []
      };
    }
    const prfData = [
      { name: 'Precision', value: data.precision },
      { name: 'Recall',    value: data.recall },
      { name: 'F1-score',  value: data.f1_score }
    ];
    const flatScores = data.results.flatMap(r => r.scores);
    const flatTrue   = data.results.flatMap(r => r.scores.map(() => r.gold_binary ? 1 : 0));
    const unique = Array.from(new Set(flatScores)).sort((a,b) => b - a);
    const maxScore = unique[0] ?? 0;
    const minScore = unique[unique.length - 1] ?? 0;
    const thresholds = [maxScore + Number.EPSILON, ...unique, minScore - Number.EPSILON];
    const rocData = thresholds.map(thr => {
      let tp=0, fp=0, tn=0, fn=0;
      flatScores.forEach((sc,i) => {
        const pred = sc >= thr;
        const gt   = flatTrue[i];
        tp += pred && gt;
        fp += pred && !gt;
        tn += !pred && !gt;
        fn += !pred && gt;
      });
      return { threshold: thr, fpr: fp/(fp+tn) || 0, tpr: tp/(tp+fn) || 0 };
    }).sort((a,b) => a.fpr - b.fpr);
    const prCurveData = thresholds.map(thr => {
      let tp=0, fp=0, fn=0;
      flatScores.forEach((sc,i) => {
        const pred = sc >= thr;
        const gt   = flatTrue[i];
        tp += pred && gt;
        fp += pred && !gt;
        fn += !pred && gt;
      });
      const precision = tp/(tp+fp) || 1;
      const recall    = tp/(tp+fn) || 0;
      return { recall, precision };
    }).sort((a,b) => a.recall - b.recall);
    const prAuc = prCurveData.reduce((area, curr, i, arr) => {
      const prev = arr[i-1] ?? curr;
      return area + ((curr.recall - prev.recall) * (curr.precision + prev.precision) / 2);
    }, 0);
    const { bin_edges = [], counts = [] } = data.score_histogram || {};
    const histData = counts.map((cnt,i) => ({ bin: `${bin_edges[i].toFixed(1)}–${bin_edges[i+1].toFixed(1)}`, count: cnt }));
    const iterData = (data.iteration_accuracy || []).map((acc,i) => ({ iteration: i + 1, accuracy: acc }));
    return { prfData, rocData, prCurveData, prAuc, histData, iterData };
  }, [data]);

  // Early return if no valid metrics
  if (!data || !Array.isArray(data.results)) {
    return (
      <Container>
        <Typography color="error">No metrics data available.</Typography>
        <Button onClick={() => navigate(-1)}>Back</Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="md">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Detailed Metrics
        </Typography>
        <Box textAlign="right" mb={2}>
          <Button variant="outlined" onClick={() => navigate(-1)}>
            Back to Benchmark
          </Button>
        </Box>

        <Typography variant="h6" gutterBottom>
          Precision / Recall / F1
        </Typography>
        <BarChart width={500} height={250} data={prfData}>
          <XAxis dataKey="name" />
          <YAxis domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
          <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
          <Bar dataKey="value" />
        </BarChart>

        <Box mt={2} mb={4}>
          <Typography variant="subtitle1">PR AUC: {(prAuc * 100).toFixed(2)}%</Typography>
          <LineChart width={500} height={250} data={prCurveData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="recall" domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
            <YAxis dataKey="precision" domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
            <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
            <Line type="monotone" dataKey="precision" dot={false} />
          </LineChart>
        </Box>

        <Divider sx={{ my: 4 }} />

        <Box display="flex" gap={4} flexWrap="wrap" justifyContent="space-between">
          {data.output_type === 'score' ? (
            <Box flex="1 1 48%">
              <Typography variant="h6" gutterBottom>ROC Curve</Typography>
              <LineChart width={400} height={250} data={rocData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="fpr" domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
                <YAxis dataKey="tpr" domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
                <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
                <Line type="monotone" dataKey="tpr" dot={false} />
              </LineChart>
            </Box>
          ) : (
            <Box flex="1 1 48%">
              <Typography variant="h6" gutterBottom>ROC Curve (Score mode)</Typography>
              <Typography color="textSecondary">Switch to “score” output to view.</Typography>
            </Box>
          )}

          <Box flex="1 1 48%">
            <Typography variant="h6" gutterBottom>Confusion Matrix</Typography>
            <Paper>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell />
                    <TableCell align="center"><strong>Pred False</strong></TableCell>
                    <TableCell align="center"><strong>Pred True</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell><strong>Actual False</strong></TableCell>
                    <TableCell align="center">{data.confusion_matrix?.TN}</TableCell>
                    <TableCell align="center">{data.confusion_matrix?.FP}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Actual True</strong></TableCell>
                    <TableCell align="center">{data.confusion_matrix?.FN}</TableCell>
                    <TableCell align="center">{data.confusion_matrix?.TP}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Paper>
          </Box>
        </Box>

        <Divider sx={{ my: 4 }} />

        <Typography variant="h6" gutterBottom>Score Distribution</Typography>
        <BarChart width={500} height={250} data={histData}>
          <XAxis dataKey="bin" angle={-45} textAnchor="end" interval={0} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" />
        </BarChart>

        <Divider sx={{ my: 4 }} />

        <Typography variant="h6" gutterBottom>Accuracy by Iteration</Typography>
        <LineChart width={500} height={250} data={iterData}>
          <XAxis dataKey="iteration" />
          <YAxis domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
          <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
          <Line type="monotone" dataKey="accuracy" dot={false} />
        </LineChart>
      </Box>
    </Container>
  );
};

export default Metrics;
