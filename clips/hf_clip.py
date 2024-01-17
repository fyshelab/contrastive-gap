import torch
import numpy as np
from clips.clip_parent import ClipParent
from transformers import CLIPModel, AutoTokenizer, CLIPConfig
from src.utils import get_checkpoint_path

from transformers.models.clip.modeling_clip import CLIPOutput

from src.config import *
import os




class HFClip(ClipParent):

    tokenizer = AutoTokenizer.from_pretrained(training_hyperparameters['hf_clip_model'])

    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        print('CLIP device ', self.device)


        self.tokenizer = AutoTokenizer.from_pretrained(training_hyperparameters['hf_clip_model'])
       

        self.temperature = 0.01 # this is default temp

        self.set_weights('default') # loads clip model and sets the logit scale param 

        '''
        load CLIP from respective checkpoint regardless of training mode
        clip training toy and training loop will handle loading from scratch or loading from checkpoint
        '''

        checkpoint_path = get_checkpoint_path()

        print('check point path for CLIP model ', checkpoint_path)

        # check if checkpoint path exists
        if os.path.exists(checkpoint_path):
            loaded_checkpoint = torch.load(checkpoint_path, map_location=self.device)

        
            # this only makes sense if we're loading from a checkpoint
            if not selected_clip_model == ClipModels.DEFAULT:
                self.load_state_dict(loaded_checkpoint['model_state_dict'])
                print('loaded clip model from checkpoint ', checkpoint_path)

            else:
                print('CLIP model not loaded from checkpoint')

        else:
            print('CLIP model not loaded from checkpoint')

        # if path doesnt exist, it means we're starting from pretrained model anyway

        self.loss = torch.nn.CrossEntropyLoss()

        print()
        print('--- HF CLIP MODEL ---')
        print()

        print('selected clip model ', selected_clip_model.name)

        # calculate temperature from logit scale and assert that its the same as temp
        assert np.isclose(self.temperature, 1 / self.model.logit_scale.exp().item())
        # print('logit scale: ', self.model.logit_scale)
        print('temperature (T): ', self.temperature)
  

        print()

        # no need to load state dict for default, since it's the same as the pretrained model


    def set_weights(self, state='default'):
        if state == 'default':
            print('-- LOADING DEFAULT CLIP MODEL --')
            self.model = CLIPModel.from_pretrained(training_hyperparameters['hf_clip_model'], )
        elif state == 'random':
            print('-- LOADING CLIP MODEL WITH RANDOM WEIGHTS FROM SCRATCH --')
            '''
            These are from https://huggingface.co/docs/transformers/v4.36.1/en/model_doc/clip#transformers.CLIPConfig
            '''
            # Initializing a CLIPConfig with openai/clip-vit-base-patch32 style configuration
            configuration = CLIPConfig()

            # Initializing a CLIPModel (with random weights) from the openai/clip-vit-base-patch32 style configuration
            self.model = CLIPModel(configuration)
            self.model.init_weights()

        # set model parameters requires_grad to True
        for param in self.model.parameters():
            param.requires_grad = True

        if selected_clip_model == ClipModels.FINETUNED_TEMP or selected_clip_model == ClipModels.WARM:

            self.temperature = training_hyperparameters['temperature']
            self.intra_modality_temperature = training_hyperparameters['intra_modality_temperature']

            self.intra_modality_logit_scale = torch.nn.Parameter(torch.tensor(np.log(1 / self.intra_modality_temperature), requires_grad=False, device=self.device)) # not self.model since clip_model doesn't have intra_modality_logit_scale

            self.intra_modality_logit_scale.requires_grad = False

            self.model.logit_scale = torch.nn.Parameter(torch.tensor(np.log(1 / self.temperature), requires_grad=False, device=self.device))

            self.model.logit_scale.requires_grad = False
        
        self.to(self.device)
        


    def encode_image(self, preprocessed_images):

        preprocessed_images = preprocessed_images.to(self.device)


        image_features = self.model.get_image_features(pixel_values=preprocessed_images)

        # return pooled_output AFTER projection
        return image_features
    
    @staticmethod
    def static_tokenize_captions(captions):

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        tokenized_captions = HFClip.tokenizer(captions, padding=True, return_tensors="pt", truncation=True, max_length=77)

        # tokenized_captions = tokenized_captions.to(device)

        return tokenized_captions


    def tokenize_captions(self, captions):
        tokenized_captions = self.tokenizer(captions, padding=True, return_tensors="pt", truncation=True, max_length=77)

        tokenized_captions = tokenized_captions.to(self.device)

        return tokenized_captions
    
    def encode_text(self, tokenized_captions):
        '''
        Returns pooled_output AFTER projection
        '''
        # # assuming raw captions input, so need to tokenize and stuff
        # tokenized_captions = self.tokenizer(captions, padding=True, return_tensors="pt")

        # tokenized_captions = tokenized_captions.to(self.device)

        # outputs = self.text_model(**tokenized_captions)

        # last_hidden_states = outputs.last_hidden_state
        # pooled_output = outputs.pooler_output # pooled (EOS token) states, text encoding just before CLIP's linear projection. shape: ([batch_size, 512])

        # return pooled_output

        # assuming raw captions input, so need to tokenize and stuff
        # tokenized_captions = self.tokenizer(captions, padding=True, return_tensors="pt")

        # tokenized_captions = tokenized_captions.to(self.device)

        # tokenized_captions = self.tokenize_captions(captions)

        text_features = self.model.get_text_features(**tokenized_captions)

        return text_features
    
    
  
    def forward(self, preprocessed_images, captions, output_loss=True, return_all=False, output_intra_modality_loss=False):

        '''
        outputs = CLIPOutput(
            loss=loss,
            logits_per_image= logits_per_image,
            logits_per_text= logits_per_text,
            text_embeds= text_embeds,
            image_embeds= image_embeds,
        )
        '''

        # inputs = self.processor(text=['captions', 'hello'], images=image, return_tensors="pt", padding=True)

        # tokenized_captions = self.tokenize_captions(captions)

        tokenized_captions = captions.to(self.device)
        preprocessed_images = preprocessed_images.to(self.device)

        outputs = self.model(input_ids=tokenized_captions['input_ids'], attention_mask=tokenized_captions['attention_mask'], pixel_values=preprocessed_images, return_loss=output_loss)


        # this is exactly the same code (although I wrote it) as huggingface clip's loss as in https://github.dev/huggingface/transformers/blob/main/src/transformers/models/clip/modeling_clip.py


        # normalize features
        image_embeds = outputs.image_embeds
        text_embeds = outputs.text_embeds

        # normalized features
        image_embeds = image_embeds / image_embeds.norm(p=2, dim=-1, keepdim=True)
        text_embeds = text_embeds / text_embeds.norm(p=2, dim=-1, keepdim=True)

        logits_per_image = outputs.logits_per_image
        logits_per_text = outputs.logits_per_text

        labels = torch.arange(logits_per_image.shape[0]).to(self.device)

        image_weight = training_hyperparameters['loss_weights']['image_to_text_weight']
        text_weight = training_hyperparameters['loss_weights']['text_to_image_weight']

        loss = 0

        if output_loss == True:

            if training_hyperparameters['intra_modality_loss']:
                # find cosine similarities between image embeddings themselves
                scaled_image_image_similarity = image_embeds @ image_embeds.t() * self.intra_modality_logit_scale.exp()

                # find cosine similarities between text embeddings themselves
                scaled_text_text_similarity = text_embeds @ text_embeds.t() * self.intra_modality_logit_scale.exp()

                intra_modality_loss = self.loss(scaled_image_image_similarity, labels) * image_weight + self.loss(scaled_text_text_similarity, labels) * text_weight

                # print('intra loss: ,', intra_modality_loss)
            inter_modality_loss = self.loss(logits_per_image, labels) * image_weight + self.loss(logits_per_text, labels) * text_weight 

            if training_hyperparameters['intra_modality_loss']:
                loss = (intra_modality_loss + inter_modality_loss) / 2
            else:
                loss = inter_modality_loss

            if output_intra_modality_loss:
                loss = {
                    'inter_modality': inter_modality_loss.item(),
                    
                    'total': loss.item(),
                }

                if training_hyperparameters['intra_modality_loss']:
                    loss['intra_modality'] = intra_modality_loss.item()
                else:
                    loss['intra_modality'] = -100

        outputs = CLIPOutput(
            loss=loss,
            logits_per_image= logits_per_image,
            logits_per_text= logits_per_text,
            text_embeds= text_embeds,
            image_embeds= image_embeds,
        )


        if return_all:
            return outputs
        
        logits_per_image = outputs.logits_per_image
        logits_per_text = outputs.logits_per_text
        if output_loss:
            
            return logits_per_image, logits_per_text, loss
        else:
            return logits_per_image, logits_per_text

            

        

    def forward_1(self, preprocessed_images, captions, scale=False):

        # inputs = self.processor(text=['captions', 'hello'], images=image, return_tensors="pt", padding=True)

        preprocessed_images = preprocessed_images.to(self.device)

        encoded_images = self.encode_image(preprocessed_images)

        encoded_captions = self.encode_text(captions)

         # normalize features
        image_features = encoded_images / torch.norm(encoded_images, dim=1, keepdim=True)
        text_features = encoded_captions / torch.norm(encoded_captions, dim=1, keepdim=True)

        if scale:
            logit_scale = self.logit_scale.exp()
            logits_per_image = logit_scale * image_features @ text_features.t()
        else:
            logits_per_image = image_features @ text_features.t()
        logits_per_text = logits_per_image.t()

        # shape = [global_batch_size, global_batch_size]
        return logits_per_image, logits_per_text
    

    def forward_old(self, preprocessed_images, captions, scale=True):

        # inputs = self.processor(text=['captions', 'hello'], images=image, return_tensors="pt", padding=True)

        preprocessed_images = preprocessed_images.to(self.device)

        caption_inputs = self.tokenizer(captions, padding=True, return_tensors="pt")

        # image_inputs = self.processor(text=captions, return_tensors="pt", padding=True)

        

        outputs = self.model(input_ids=caption_inputs['input_ids'].to(self.device), attention_mask=caption_inputs['attention_mask'].to(self.device), pixel_values=preprocessed_images)

        logits_per_image, logits_per_text = outputs.logits_per_image, outputs.logits_per_text

        logits_per_image, logits_per_text = logits_per_image / 100, logits_per_text / 100

        return logits_per_image, logits_per_text
    
