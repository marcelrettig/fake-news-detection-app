import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Container, Box, Typography, Button, Divider,
  Slider,
  Table, TableBody, TableCell, TableHead, TableRow, Paper,
  CircularProgress
} from '@mui/material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, LabelList
} from 'recharts';

const Metrics = () => {
  const { state } = useLocation();
  const navigate = useNavigate();

  // pulled in from Benchmark.js
  const data = state.metrics;
  const { plotImages, loadingPlots, plotError } = state;

  const {
        id,
        use_external_info: useExternalInfo,
        output_type: outputType,
        prompt_variant: promptVariant
      } = data;

  // Slider state for threshold
  const [threshold, setThreshold] = useState(0.5);
  const handleThresholdChange = (_, value) => setThreshold(value);

  // Memoize data to avoid recreating on every render
  const raw = data;
  const {
    flatScores,
    flatTrue,
    flatPreds,
    rocData,
    prCurveData,
    prAuc,
    histData,
    iterData
  } = useMemo(() => {
    if (!data || !Array.isArray(data.results)) {
      return {
        flatScores: [], flatTrue: [], flatPreds: [],
        rocData: [], prCurveData: [], prAuc: 0,
        histData: [], iterData: []
      };
    }

    // (same flattening + roc/pr/hist/iter logic as before)
    let flatScores = [], flatTrue = [], flatPreds = [];

    if (data.output_type === 'score' || data.output_type === 'score_expl') {
      flatScores = data.results.flatMap(r => r.scores);
      flatTrue   = data.results.flatMap(r => r.scores.map(() => r.gold_binary ? 1 : 0));
      const unique     = Array.from(new Set(flatScores)).sort((a, b) => b - a);
      const maxScore   = unique[0] ?? 0;
      const minScore   = unique[unique.length - 1] ?? 0;
      const thresholds = [maxScore + Number.EPSILON, ...unique, minScore - Number.EPSILON];

      const rocData = thresholds.map(thr => {
        let tp = 0, fp = 0, tn = 0, fn = 0;
        flatScores.forEach((sc, i) => {
          const pred = sc >= thr;
          const gt   = flatTrue[i];
          if      (pred && gt ) tp++;
          else if (pred && !gt) fp++;
          else if (!pred && !gt) tn++;
          else if (!pred && gt ) fn++;
        });
        return {
          threshold: thr,
          fpr: fp / (fp + tn) || 0,
          tpr: tp / (tp + fn) || 0
        };
      }).sort((a, b) => a.fpr - b.fpr);

      const prCurveData = thresholds.map(thr => {
        let tp = 0, fp = 0, fn = 0;
        flatScores.forEach((sc, i) => {
          const pred = sc >= thr;
          const gt   = flatTrue[i];
          if      (pred && gt ) tp++;
          else if (pred && !gt) fp++;
          else if (!pred && gt ) fn++;
        });
        const precision = tp / (tp + fp) || 1;
        const recall    = tp / (tp + fn) || 0;
        return { recall, precision };
      }).sort((a, b) => a.recall - b.recall);
      const prAuc = prCurveData.reduce((area, curr, i, arr) => {
        const prev = arr[i - 1] ?? curr;
        return area + ((curr.recall - prev.recall) * (curr.precision + prev.precision) / 2);
      }, 0);

      const { bin_edges = [], counts = [] } = data.score_histogram || {};
      const histData = counts.map((cnt, i) => ({
        bin: `${bin_edges[i].toFixed(1)}–${bin_edges[i + 1].toFixed(1)}`,
        count: cnt
      }));

      const iterData = (data.iteration_accuracy || []).map((acc, i) => ({
        iteration: i + 1,
        accuracy: acc
      }));

      return { flatScores, flatTrue, flatPreds: [], rocData, prCurveData, prAuc, histData, iterData };
    }

    if (data.output_type === 'binary' || data.output_type === 'binary_expl') {
      flatTrue  = data.results.map(r => r.gold_binary ? 1 : 0);
      flatPreds = data.results.map(r => {
        const votes = r.scores.filter(v => v >= 0.5).length;
        return votes > r.scores.length / 2 ? 1 : 0;
      });

      const { bin_edges = [], counts = [] } = data.score_histogram || {};
      const histData = counts.map((cnt, i) => ({
        bin: `${bin_edges[i].toFixed(1)}–${bin_edges[i + 1].toFixed(1)}`,
        count: cnt
      }));
      const iterData = (data.iteration_accuracy || []).map((acc, i) => ({
        iteration: i + 1,
        accuracy: acc
      }));

      return { flatScores: [], flatTrue, flatPreds, rocData: [], prCurveData: [], prAuc: 0, histData, iterData };
    }

    return { flatScores: [], flatTrue: [], flatPreds: [], rocData: [], prCurveData: [], prAuc: 0, histData: [], iterData: [] };
  }, [data]);
  
  const { prfData, confusion } = useMemo(() => {
    // If Firestore picked up a confusion matrix for binary mode, use it directly:
    if ((data.output_type === 'binary' || data.output_type === 'binary_expl') && data.confusion_matrix) {
      const { TP, FP, FN, TN } = data.confusion_matrix;
      // precision/recall here are already for the “Fake” class (False)
      const precision = TP / (TP + FP) || 0;
      const recall    = TP / (TP + FN) || 0;
      const f1        = (precision + recall)
        ? 2 * precision * recall / (precision + recall)
        : 0;
      // Only makes sense when true news in dataset, have to update issue!!!
      const specificity = TN / (TN + FP) || 0;
      const balanced = (recall + specificity) / 2;
      return {
        prfData: [
          { name: 'Precision', value: precision },
          { name: 'Recall',    value: recall    },
          { name: 'F1-Score',  value: f1        },
          { name: 'BACC',value: balanced  }
        ],
        confusion: { TP, FP, FN, TN }
      };
    }
  
    // Otherwise, recompute manually but treating “Fake” (false) as positive:
    let TP = 0, FP = 0, TN = 0, FN = 0;
  
    if (data.output_type === 'binary' || data.output_type === 'binary_expl') {
      // Majority‐vote per statement
      data.results.forEach(r => {
        const vote = r.scores.filter(v => v >= 0.5).length > r.scores.length / 2;
        const predFake = !vote;
        const gtFake   = !r.gold_binary;
        if      (predFake && gtFake) TP++;
        else if (predFake && !gtFake) FP++;
        else if (!predFake && !gtFake) TN++;
        else if (!predFake && gtFake) FN++;
      });
    } else {
      // Score/detailed: one thresholded entry per individual score
      data.results.forEach(r => {
        r.scores.forEach(sc => {
          const vote     = sc >= threshold;
          const predFake = !vote;
          const gtFake   = !r.gold_binary;
          if      (predFake && gtFake) TP++;
          else if (predFake && !gtFake) FP++;
          else if (!predFake && !gtFake) TN++;
          else if (!predFake && gtFake) FN++;
        });
      });
    }
  
    const precision = TP / (TP + FP) || 0;
    const recall    = TP / (TP + FN) || 0;
    const f1        = (precision + recall)
      ? 2 * precision * recall / (precision + recall)
      : 0;
    const specificity = TN / (TN + FP) || 0;
    const balanced = (recall + specificity) / 2;
  
    return {
      prfData: [
        { name: 'Precision', value: precision },
        { name: 'Recall',    value: recall    },
        { name: 'F1-Score',  value: f1        },
        { name: 'BACC',value: balanced  }
      ],
      confusion: { TP, FP, FN, TN }
    };
  }, [data, threshold]);

  if (!data || !Array.isArray(data.results)) {
    return (
      <Container>
        <Typography color="error">No metrics data available.</Typography>
        <Button onClick={() => navigate(-1)}>Back</Button>
      </Container>
    );
  }

  const isScoreMode = data.output_type === 'score' || data.output_type === 'score_expl';

  return (
    <Container maxWidth="md">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Detailed Metrics
        </Typography>

        <Box textAlign="center" mb={3}>
        <Typography variant="body1"><strong>ID:</strong> {id}</Typography>
        <Typography variant="body2"><strong>Use External Info:</strong> {useExternalInfo ? 'Yes' : 'No'}</Typography>
        <Typography variant="body2"><strong>Output Format:</strong> {outputType}</Typography>
        <Typography variant="body2"><strong>Prompt Variant:</strong> {promptVariant}</Typography>
      </Box>

        <Box textAlign="right" mb={2}>
          <Button variant="outlined" onClick={() => navigate(-1)}>
            Back to Benchmark
          </Button>
        </Box>

        {/* Precision / Recall / F1 */}
        <Typography variant="h6" gutterBottom>
          Precision / Recall / F1 / BACC
        </Typography>
        <BarChart width={500} height={250} data={prfData}>
          <XAxis dataKey="name" />
          <YAxis domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
          <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
          <Bar dataKey="value">
            <LabelList
              dataKey="value"
              position="inside"
              fill="#ffffff" 
              formatter={v => `${(v*100).toFixed(1)}%`}
            />
          </Bar>
        </BarChart>

        {isScoreMode && (
          <>
            {/* Threshold Slider */}
            <Box my={2}>
              <Typography gutterBottom>
                Threshold: {(threshold * 100).toFixed(0)}%
              </Typography>
              <Slider
                value={threshold}
                onChange={handleThresholdChange}
                step={0.05}
                min={0}
                max={1}
                valueLabelDisplay="auto"
                marks
              />
            </Box>

            {/* PR Curve image */}
            <Box mt={2} mb={4}>
              <Typography variant="subtitle1">
                PR AUC: {(prAuc * 100).toFixed(2)}%
              </Typography>
              {loadingPlots ? (
                <CircularProgress />
              ) : plotError ? (
                <Typography color="error">Failed to load PR curve.</Typography>
              ) : (
                <img
                  src={`data:image/png;base64,${plotImages.pr_auc_curve}`}
                  alt="Precision–Recall Curve"
                  style={{ maxWidth: '100%' }}
                />
              )}
            </Box>
          </>
        )}

        <Divider sx={{ my: 4 }} />

        <Box display="flex" gap={4} flexWrap="wrap" justifyContent="space-between">
          {/* ROC Curve image */}
          <Box flex="1 1 48%">
            <Typography variant="h6" gutterBottom>ROC Curve</Typography>
            {isScoreMode ? (
              loadingPlots ? (
                <CircularProgress />
              ) : plotError ? (
                <Typography color="error">Failed to load ROC curve.</Typography>
              ) : (
                <img
                  src={`data:image/png;base64,${plotImages.roc_curve}`}
                  alt="ROC Curve"
                  style={{ maxWidth: '100%' }}
                />
              )
            ) : (
              <Typography color="textSecondary">Not available in binary mode.</Typography>
            )}
          </Box>

          {/* Confusion Matrix */}
          <Box flex="1 1 48%">
            <Typography variant="h6" gutterBottom>Confusion Matrix</Typography>
            <Paper>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell />
                    <TableCell align="center"><strong>Pred Fake</strong></TableCell>
                    <TableCell align="center"><strong>Pred TrueNews</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell><strong>Actual Fake</strong></TableCell>
                    <TableCell align="center">TP: {confusion.TP}</TableCell>
                    <TableCell align="center">FN: {confusion.FN}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell><strong>Actual TrueNews</strong></TableCell>
                    <TableCell align="center">FP: {confusion.FP}</TableCell>
                    <TableCell align="center">TN: {confusion.TN}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Paper>
          </Box>
        </Box>

        <Divider sx={{ my: 4 }} />

        {/* Score Distribution */}
        <Typography variant="h6" gutterBottom>Score Distribution</Typography>
        <BarChart width={500} height={250} data={histData}>
          <XAxis dataKey="bin" angle={-45} textAnchor="end" interval={0} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" />
        </BarChart>

        <Divider sx={{ my: 4 }} />

        {/* Accuracy by Iteration */}
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
