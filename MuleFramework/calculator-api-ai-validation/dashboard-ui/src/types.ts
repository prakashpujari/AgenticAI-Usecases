export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type Recommendation = 'APPROVED' | 'CONDITIONAL' | 'BLOCKED';

export interface AgentFinding {
  severity: Severity;
  title: string;
  detail: string;
  recommendation: string | null;
}

export interface AgentReport {
  agent: string;
  score: number;
  summary: string;
  findings: AgentFinding[];
  raw_llm_output: string | null;
}

export interface ExecutiveDashboard {
  application: string;
  runtime: string;
  coverage: number;
  testsExecuted: number;
  testsPassed: number;
  testsFailed: number;
  passRate: number;
  securityScore: number;
  performanceScore: number;
  confidenceScore: number;
  riskScore: number;
  productionReadiness: number;
  recommendation: Recommendation;
}

export interface PipelineResponse {
  dashboard: ExecutiveDashboard;
  agent_reports: AgentReport[];
  executive_summary: string;
  artifacts: {
    munit_total: number;
    munit_failures: number;
    munit_coverage: number;
  };
}

export interface PipelineRequest {
  munit_reports_dir: string;
  raml_path: string;
  mule_xml_dir: string;
  application: string;
  runtime: string;
}
