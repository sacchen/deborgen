// go run cmd/worker/main.go --coordinator http://localhost:8000 --node-id go-node-1

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

type HeartbeatRequest struct {
	Name   *string                `json:"name"`
	Labels map[string]interface{} `json:"labels"`
}

func sendHeartbeat(coordinator, nodeID, token string) {
	labels := map[string]interface{}{
		"os":        runtime.GOOS,
		"arch":      runtime.GOARCH,
		"cpu_cores": runtime.NumCPU(),
	}

	payload := HeartbeatRequest{
		Name:   nil,
		Labels: labels,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("heartbeat failed to serialize: %v", err)
		return
	}

	url := fmt.Sprintf("%s/nodes/%s/heartbeat", coordinator, nodeID)

	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		log.Printf("heartbeat failed: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("heartbeat failed: %v", err)
		return
	}
	resp.Body.Close()
	log.Printf("heartbeat sent: %d", resp.StatusCode)
}

type JobResponse struct {
	Job struct {
		ID             string `json:"id"`
		Command        string `json:"command"`
		TimeoutSeconds int    `json:"timeout_seconds"`
	} `json:"job"`
	LeaseToken string `json:"lease_token"`
}

func pollNextJob(coordinator, nodeID, token string) (string, string, string, int, bool) {
	url := fmt.Sprintf("%s/jobs/next?node_id=%s", coordinator, nodeID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		log.Printf("poll next job failed: %v", err)
		return "", "", "", 0, false
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("poll next job failed: %v", err)
		return "", "", "", 0, false
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", "", "", 0, false
	}

	var result JobResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Printf("poll failed to parse response: %v", err)
		return "", "", "", 0, false
	}
	return result.Job.ID, result.Job.Command, result.LeaseToken, result.Job.TimeoutSeconds, true
}

func runJob(command string, timeoutSeconds int) (int, string, string) {
	args := strings.Fields(command)
	if len(args) == 0 {
		return 2, "", "invalid command: empty command"
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSeconds)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	output, err := cmd.CombinedOutput()

	if ctx.Err() == context.DeadlineExceeded {
		return 124, string(output), fmt.Sprintf("timeout exceeded (%ds)", timeoutSeconds)
	}

	if err != nil {
		return 127, string(output), fmt.Sprintf("command failed: %v", err)
	}

	return 0, string(output), ""
}

type UploadLogsRequest struct {
	NodeID     string `json:"node_id"`
	LeaseToken string `json:"lease_token"`
	Text       string `json:"text"`
}

func uploadLogs(coordinator, jobID, nodeID, leaseToken, token, text string) {
	payload := UploadLogsRequest{
		NodeID:     nodeID,
		LeaseToken: leaseToken,
		Text:       text,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("upload logs failed to serialize: %v", err)
		return
	}

	url := fmt.Sprintf("%s/jobs/%s/logs", coordinator, jobID)

	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		log.Printf("upload logs failed: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("upload logs failed: %v", err)
		return
	}
	resp.Body.Close()
	log.Printf("upload logs sent: %d", resp.StatusCode)
}

type FinishJobRequest struct {
	NodeID        string `json:"node_id"`
	LeaseToken    string `json:"lease_token"`
	ExitCode      int    `json:"exit_code"`
	FailureReason string `json:"failure_reason"`
}

func finishJob(coordinator, jobID, nodeID, leaseToken, token string, exitCode int, failureReason string) {
	payload := FinishJobRequest{
		NodeID:        nodeID,
		LeaseToken:    leaseToken,
		ExitCode:      exitCode,
		FailureReason: failureReason,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("finish job failed to serialize: %v", err)
		return
	}

	url := fmt.Sprintf("%s/jobs/%s/finish", coordinator, jobID)

	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		log.Printf("finish job failed: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("finish job failed: %v", err)
		return
	}
	resp.Body.Close()
	log.Printf("finish job sent: %d", resp.StatusCode)
}

func main() {
	coordinator := flag.String("coordinator", "", "coordinator URL")
	nodeID := flag.String("node-id", "", "node identifier")
	token := flag.String("token", "", "bearer token")
	flag.Parse()

	// heartbeat runs in the background
	go func() {
		sendHeartbeat(*coordinator, *nodeID, *token)

		ticker := time.NewTicker(15 * time.Second)
		defer ticker.Stop()

		for range ticker.C {
			sendHeartbeat(*coordinator, *nodeID, *token)
		}
	}()

	// main loop polls for jobs
	for {
		jobID, command, leaseToken, timeoutSeconds, ok := pollNextJob(*coordinator, *nodeID, *token)
		if !ok { // if queue is empty, sleep
			time.Sleep(2 * time.Second)
			continue
		}

		log.Printf("running job %s: %s", jobID, command)
		exitCode, output, failureReason := runJob(command, timeoutSeconds)
		uploadLogs(*coordinator, jobID, *nodeID, leaseToken, *token, output)
		finishJob(*coordinator, jobID, *nodeID, leaseToken, *token, exitCode, failureReason)
	}

}
