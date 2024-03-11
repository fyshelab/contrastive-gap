import torch
from transformers import CLIPTextConfig, CLIPTextModelWithProjection

from transformers.models.clip.modeling_clip import CLIPOutput

from src.config import *

from clips.encoder import Encoder


 
class TextEncoder(Encoder):


    # init
    def __init__(self, tokenizer, CLIPTextConfig: CLIPTextConfig, from_pretrained=False, name='Untitled Text Encoder'):
        '''
        Set CLIPTextConfig with appropriate vocab size if using diff tokenizers
        '''
        super().__init__()

        self.tokenizer = tokenizer

        self.name = name

        self.pooler_layer_norm = torch.nn.LayerNorm(CLIPTextConfig.hidden_size, eps=CLIPTextConfig.layer_norm_eps, elementwise_affine=False) # no trainable params
        

        self.CLIPTextConfig = CLIPTextConfig
        self.hidden_size = CLIPTextConfig.hidden_size

        self.device = torch.device(training_hyperparameters['cuda_device'] if torch.cuda.is_available() else "cpu")

        if from_pretrained:
            print()
            print(f" --- Initializing {name} from pretrained model ---")
            print()
            self.text_model = CLIPTextModelWithProjection.from_pretrained(training_hyperparameters['hf_clip_model']).to(self.device)

        else:
            print()
            print(f" --- Initializing {name} from scratch --- ")
            print()
            
            self.text_model = CLIPTextModelWithProjection(CLIPTextConfig).to(self.device)
            self.text_model.init_weights()


            
            

        for param in self.text_model.parameters():
            param.requires_grad = True



    def forward(self, captions, output_hidden_states=False):

        tokenized_captions = self.tokenize_captions(captions)

        outputs = self.text_model(**tokenized_captions, output_hidden_states=output_hidden_states)

        return {
            'embeds': outputs.text_embeds,
            'hidden_states': outputs.hidden_states if output_hidden_states else None,
            'input_ids': tokenized_captions['input_ids']
        }



    def tokenize_captions(self, captions):
        return self.tokenizer(captions, padding=True, truncation=True, return_tensors="pt").to(self.device)
    

    def pool_hidden_state(self, hidden_state: torch.FloatTensor, input_ids: torch.Tensor):
        '''
        `hidden_state` is `torch.FloatTensor` of shape `(batch_size, sequence_length, hidden_size)`
        `LayerNorm` without trainable params before pooling
        Need to normalize since we'll eventually compute cosine similarity, but maybe dont do that here?
        '''

        assert hidden_state.shape[2] == self.CLIPTextConfig.hidden_size

        layer_normed_hidden_state = self.pooler_layer_norm(hidden_state)

        # this is from CLIPTextTransformer in https://github.dev/huggingface/transformers/blob/v4.38.2/src/transformers/models/clip/modeling_clip.py

        if self.CLIPTextConfig.eos_token_id == 2:
            # The `eos_token_id` was incorrect before PR #24773: Let's keep what have been done here.
            # A CLIP model with such `eos_token_id` in the config can't work correctly with extra new tokens added
            # ------------------------------------------------------------
            # text_embeds.shape = [batch_size, sequence_length, transformer.width]
            # take features from the eot embedding (eot_token is the highest number in each sequence)
            # casting to torch.int for onnx compatibility: argmax doesn't support int64 inputs with opset 14
            pooled_output = layer_normed_hidden_state[
                torch.arange(layer_normed_hidden_state.shape[0], device=layer_normed_hidden_state.device),
                input_ids.to(dtype=torch.int, device=layer_normed_hidden_state.device).argmax(dim=-1),
            ]
        else:
            # The config gets updated `eos_token_id` from PR #24773 (so the use of exta new tokens is possible)
            pooled_output = layer_normed_hidden_state[
                torch.arange(layer_normed_hidden_state.shape[0], device=layer_normed_hidden_state.device),
                # We need to get the first position of `eos_token_id` value (`pad_token_ids` might equal to `eos_token_id`)
                (input_ids.to(dtype=torch.int, device=layer_normed_hidden_state.device) == self.CLIPTextConfig.eos_token_id)
                .int()
                .argmax(dim=-1),
            ]


        # pooled_output shape = [batch_size, CLIPTextConfig.hidden_size]
            
        assert pooled_output.shape[1] == self.CLIPTextConfig.hidden_size, f"pooled_output.shape = {pooled_output.shape}, CLIPTextConfig.hidden_size = {self.CLIPTextConfig.hidden_size}"

        assert pooled_output.shape[0] == hidden_state.shape[0], f"pooled_output.shape = {pooled_output.shape}, hidden_state.shape = {hidden_state.shape}"

        return pooled_output





        