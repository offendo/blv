#!/bin/bash

seq 1 $N_WORKERS | xargs -P$N_WORKERS -I@ bash -c 'export REPL_PORT=$((1344+@)); rq worker -q --worker-class \'src.pyleanrepl.worker.VerifierWorker' '

wait
