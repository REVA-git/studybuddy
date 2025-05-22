MODEL := google/gemma-3-1b-it
DATA_PATH := data
BATCH_SIZE := 2
ITERATIONS := 1000
MAX_TOKENS := 1000

# MODEL := meta-llama/Llama-3.2-3B-Instruct

generate: 
	mlx_lm.generate --model $(MODEL) --prompt "Who programs are offered??" --max-tokens $(MAX_TOKENS)

# train mlx model + adapter
train:
	mlx_lm.lora --model $(MODEL) --train --data $(DATA_PATH) --iter $(ITERATIONS) --batch-size $(BATCH_SIZE)  

evaluate:
	mlx_lm.lora --model $(MODEL) --adapter-path ./adapters --data $(DATA_PATH) --test

validate:
	mlx_lm.generate --model $(MODEL) --prompt "What are some facilities in REVA University?" --adapter-path ./adapters --max-tokens $(MAX_TOKENS)

generate_adapter: 
	mlx_lm.generate --model $(MODEL) --prompt "What are some facilities in REVA University?" --adapter-path ./adapters --max-tokens $(MAX_TOKENS)

fuse:
	mlx_lm.fuse --model $(MODEL) --adapter-path ./adapters

convert:
	mlx_lm.convert --hf-path $(MODEL) --mlx-path ./ollama_model/

# create ollama model from mlx model + adapter
create:
	ollama create gemmmma3:1b -f Modelfile

# run ollama model
run:
	ollama run gemmmma3:1b

# run mlx server
server:
	mlx_lm.server --model mlx-community/gemma-3-1b-it-qat-4bit