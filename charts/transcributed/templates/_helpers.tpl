{{- define "transcributed.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "transcributed.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "transcributed.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "transcributed.labels" -}}
helm.sh/chart: {{ include "transcributed.chart" . }}
{{ include "transcributed.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "transcributed.selectorLabels" -}}
app.kubernetes.io/name: {{ include "transcributed.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "transcributed.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "transcributed.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "transcributed.apiImage" -}}
{{- printf "%s:%s" .Values.api.image.repository (default .Chart.AppVersion .Values.api.image.tag) }}
{{- end }}

{{- define "transcributed.workerImage" -}}
{{- printf "%s:%s" .Values.worker.image.repository (default .Chart.AppVersion .Values.worker.image.tag) }}
{{- end }}

{{- define "transcributed.nasClaimName" -}}
{{- if .Values.nas.existingClaim }}
{{- .Values.nas.existingClaim }}
{{- else if .Values.nas.create }}
{{- printf "%s-nas" (include "transcributed.fullname" .) }}
{{- else }}
{{- fail "nas.existingClaim is required when nas.enabled=true and nas.create=false" }}
{{- end }}
{{- end }}

{{- define "transcributed.envFrom" -}}
envFrom:
  - configMapRef:
      name: {{ include "transcributed.fullname" . }}
  - secretRef:
      name: {{ .Values.secrets.name }}
{{- end }}
