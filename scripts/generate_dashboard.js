#!/usr/bin/env node
/**
 * Generate HTML Dashboard with analysis data
 * Usage: node generate_dashboard.js input.json [output.html]
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 1) {
    console.error('Usage: node generate_dashboard.js input.json [output.html]');
    process.exit(1);
  }
  
  const inputFile = args[0];
  const outputFile = args[1] || 'dashboard.html';
  
  // Check if input file exists
  if (!fs.existsSync(inputFile)) {
    console.error(`Input file not found: ${inputFile}`);
    process.exit(1);
  }
  
  // Run the CARL engine
  console.log('Running CARL analysis...');
  const enginePath = path.join(__dirname, '..', 'cli.js');
  const result = execSync(`node "${enginePath}" "${inputFile}"`, { encoding: 'utf8' });
  
  let analysisData;
  try {
    analysisData = JSON.parse(result);
  } catch (e) {
    console.error('Failed to parse engine output:', e.message);
    process.exit(1);
  }
  
  // Transform engine output to dashboard format
  const dashboardData = transformToDashboardFormat(analysisData);
  
  // Read HTML template
  const templatePath = path.join(__dirname, '..', 'resources', 'html', 'analyse.HTML');
  let htmlContent = fs.readFileSync(templatePath, 'utf8');
  
  // Inject analysis data
  const injection = `<script>window.ANALYSIS_DATA = ${JSON.stringify(dashboardData, null, 2)};</script>`;
  htmlContent = htmlContent.replace('<!--__INJECT_ANALYSIS_DATA__-->', injection);
  
  // Copy assets to output directory if needed
  const outputDir = path.dirname(path.resolve(outputFile));
  const assetsSource = path.join(__dirname, '..', 'resources', 'html', 'assets');
  const assetsTarget = path.join(outputDir, 'assets');
  
  if (!fs.existsSync(assetsTarget)) {
    fs.mkdirSync(assetsTarget, { recursive: true });
    const assets = fs.readdirSync(assetsSource);
    assets.forEach(file => {
      fs.copyFileSync(
        path.join(assetsSource, file),
        path.join(assetsTarget, file)
      );
    });
    console.log(`Copied assets to ${assetsTarget}`);
  }
  
  // Write output file
  fs.writeFileSync(outputFile, htmlContent, 'utf8');
  console.log(`Dashboard generated: ${outputFile}`);
  
  // Also save the raw analysis data
  const dataFile = outputFile.replace('.html', '_data.json');
  fs.writeFileSync(dataFile, JSON.stringify(dashboardData, null, 2), 'utf8');
  console.log(`Analysis data saved: ${dataFile}`);
}

function transformToDashboardFormat(engineOutput) {
  // Count markers by family
  const families = {};
  const clusterScores = {};
  
  // Process markers
  (engineOutput.markers || []).forEach(marker => {
    const family = extractFamily(marker.id);
    if (!families[family]) families[family] = 0;
    families[family]++;
  });
  
  // Process promoted markers (CLU level)
  const cluMarkers = engineOutput.markers?.filter(m => 
    m.type === 'CLU' || m.id?.startsWith('CLU_')
  ) || [];
  
  cluMarkers.forEach(marker => {
    const family = extractFamily(marker.id);
    clusterScores[family] = (clusterScores[family] || 0) + 1;
  });
  
  // Calculate drift (placeholder - would need proper implementation)
  const drift = {
    direction: "neutral",
    magnitude: 0.0,
    confidence: 0.0
  };
  
  // Get top clusters
  const topClusters = Object.entries(clusterScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([family, score]) => [family, score]);
  
  // Extract raw text from segments
  const rawText = engineOutput.segments
    ?.map(seg => `${seg.who}: ${seg.text}`)
    .join('\n') || '';
  
  // Build benchmarks if available
  const benchmarks = engineOutput._bench || {
    runs: [{
      name: 'default',
      top_clusters: topClusters
    }]
  };
  
  return {
    model: 'carl-engine-js',
    axes: [],
    result: {
      summary: {
        top_clusters: topClusters.length > 0 ? topClusters : [['NONE', 0]],
        drift: drift,
        total_markers: engineOutput.markers?.length || 0,
        by_type: engineOutput.counts?.total || {}
      },
      details: {
        sem: engineOutput.markers?.filter(m => m.type === 'SEM').map(formatMarker) || [],
        clu: cluMarkers.map(formatMarker),
        mema: engineOutput.markers?.filter(m => m.type === 'MEMA').map(formatMarker) || [],
        ato: engineOutput.markers?.filter(m => m.type === 'ATO').map(formatMarker) || []
      }
    },
    raw_text: rawText,
    telemetry: {
      elapsed_ms: engineOutput.meta?.elapsed_ms || 0,
      engine_hash: engineOutput.meta?.engine_hash || '',
      canon_hash: engineOutput.meta?.canon_hash || ''
    },
    _bench: benchmarks
  };
}

function extractFamily(markerId) {
  // Extract family name from marker ID
  // e.g., "ATO_SUPPORT_LEX" -> "SUPPORT"
  // e.g., "SEM_VALIDATION" -> "VALIDATION"
  const parts = markerId.split('_');
  if (parts.length >= 2) {
    // Remove type prefix (ATO, SEM, CLU, MEMA)
    return parts.slice(1).join('_');
  }
  return markerId;
}

function formatMarker(marker) {
  return {
    name: marker.id,
    family: extractFamily(marker.id),
    span: marker.span || [0, 0],
    score: 1.0, // Default score
    meta: {
      segment: marker.segment_idx || 0,
      who: marker.who || 'unknown',
      evidence: marker.evidence || ''
    }
  };
}

// Run the script
main();