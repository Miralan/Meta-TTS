import torch
import torchaudio
import argparse
import os
import torch.nn as nn
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
from argparse import ArgumentParser
import json
import random

import config

import matplotlib.pyplot as plt
from pylab import plot, show, savefig, xlim, figure, \
                ylim, legend, boxplot, setp, axes

encoder = VoiceEncoder()

class CentroidSimilarity:
    def __init__(self):
        self.corpus = config.corpus
        self.data_dir_dict = config.data_dir_dict
        self.n_speaker = config.n_speaker
        self.n_sample = config.n_sample
        self.mode_list = config.mode_list
        self.step_list = config.step_list
        self.centroid_sim_mode_list = config.centroid_sim_mode_list
        with open(os.path.join(config.data_dir_dict['recon'], 'test_SQids.json'), 'r+') as F:
            self.sq_list = json.load(F)

    def load_dvector(self):
        self.dvector_list_dict = dict()
        for mode in ['recon', 'centroid', 'real']:
            self.dvector_list_dict[mode] = np.load(f'npy/{self.corpus}/{mode}_dvector.npy', allow_pickle=True)
        for mode in self.mode_list:
            for step in self.step_list:
                if mode in ['scratch_encoder', 'encoder', 'dvec'] and step != 0:
                    continue
                self.dvector_list_dict[f'{mode}_step{step}'] = np.load(f'npy/{self.corpus}/{mode}_step{step}_dvector.npy', allow_pickle=True)

    # get the cosine similarity between the centroid and the dvectors of sample utterances
    def get_centroid_similarity(self):

        cos = nn.CosineSimilarity(dim=1, eps=1e-6)
        
        # transform numpy array into torch tensor
        self.dvector_list_dict_tensor = dict()
        self.dvector_list_dict_tensor['centroid'] =  torch.from_numpy(
            np.repeat(self.dvector_list_dict['centroid'], self.n_sample, axis=0)
        )
        self.dvector_list_dict_tensor['shuffled_centroid'] = self.custom_shuffle(
            self.dvector_list_dict['centroid']
        )
        self.dvector_list_dict_tensor['recon'] = torch.from_numpy(self.dvector_list_dict['recon'])
        for mode in self.mode_list:
            for step in self.step_list:
                if mode in ['scratch_encoder', 'encoder', 'dvec'] and step != 0:
                    continue
                self.dvector_list_dict_tensor[f'{mode}_step{step}'] = torch.from_numpy(
                    self.dvector_list_dict[f'{mode}_step{step}']
                )

        # compute similarity between the centroid and the dvector of sample utterances
        self.similarity_list_dict = dict()
        with torch.no_grad():
            print(f'processing the similarity of mode: recon_random')
            self.similarity_list_dict['recon_random'] = cos(
                self.dvector_list_dict_tensor['shuffled_centroid'],
                self.dvector_list_dict_tensor['recon']
            ).detach().cpu().numpy()
            print(f'processing the similarity of mode: recon')
            self.similarity_list_dict['recon'] = cos(
                self.dvector_list_dict_tensor['centroid'],
                self.dvector_list_dict_tensor['recon']
            ).detach().cpu().numpy()
            for mode in self.mode_list:
                print(f'processing the similarity of mode: {mode}')
                for step in self.step_list:
                    if mode in ['scratch_encoder', 'encoder', 'dvec'] and step != 0:
                        continue
                    print(f'    step{step}')
                    self.similarity_list_dict[f'{mode}_step{step}'] = cos(
                        self.dvector_list_dict_tensor['centroid'],
                        self.dvector_list_dict_tensor[f'{mode}_step{step}']
                    ).detach().cpu().numpy()
   
    def save_centroid_similarity(self):
        for key in self.similarity_list_dict:
            print(key, np.mean(self.similarity_list_dict[key]), np.std(self.similarity_list_dict[key]))
        np.save(f'npy/{self.corpus}/centroid_similarity_dict.npy', self.similarity_list_dict, allow_pickle=True)

    def load_centroid_similarity(self):
        self.similarity_list_dict = np.load(f'npy/{self.corpus}/centroid_similarity_dict.npy', allow_pickle=True)[()]

    def custom_shuffle(self, centroid_list):
        centroid_list_repeat = np.repeat(centroid_list, self.n_sample, axis=0)

        break_sig =0
        while not break_sig:
            map_list = [0 for i in range(self.n_speaker*self.n_sample)]
            count_list = [0 for i in range(self.n_speaker)]
            for i in range(self.n_speaker):
                sample_list = []
                for j in range(self.n_speaker):
                    if i==j:
                        continue
                    else:
                        sample_list = sample_list + [j]*(self.n_sample-count_list[j])
                if i==self.n_speaker-1:
                    if len(sample_list)<self.n_sample:
                        print('retry')
                        continue
                    else:
                        break_sig=1
                #random sampling 16 elements from sample_list without replacement
                target_list = random.sample(sample_list, self.n_sample)
                # assign new index
                for t in range(self.n_sample):
                    map_list[i*self.n_sample + t] = target_list[t]*self.n_sample + count_list[target_list[t]]
                    count_list[target_list[t]] += 1
        #check
        count_list_check = [0 for i in range(self.n_speaker)]
        for speaker_id in range(self.n_speaker):
            for sample_id in range(self.n_sample):
                data_id  = speaker_id*self.n_sample + sample_id
                assert(map_list[data_id]//self.n_sample!=speaker_id)
                count_list_check[map_list[data_id]//self.n_sample] +=1
        for i in range(self.n_speaker):
            assert(count_list_check[i]==self.n_sample)

        shuffled_centroid_list_repeat = []
        for i in range(self.n_speaker*self.n_sample):
            shuffled_centroid_list_repeat.append(centroid_list_repeat[map_list[i],:])
        shuffled_centroid_list_repeat = np.array(shuffled_centroid_list_repeat)

        shuffled_centroid_list_repeat = torch.from_numpy(shuffled_centroid_list_repeat)

        return shuffled_centroid_list_repeat

if __name__ == '__main__':
    main = CentroidSimilarity()
    main.load_dvector()
    main.get_centroid_similarity()
    main.save_centroid_similarity()
    #main.load_centroid_similarity()
