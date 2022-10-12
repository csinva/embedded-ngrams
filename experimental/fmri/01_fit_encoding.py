import os
import sys
import numpy as np
import h5py
import argparse
import json
import pathlib
from os.path import join, dirname
import logging

# from .encoding_utils import *
import encoding_utils
from feature_spaces import _FEATURE_CONFIG, get_feature_space, repo_dir, em_data_dir, data_dir, results_dir
from ridge_utils.ridge import bootstrap_ridge


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--subject", type=str, default='UTS03')
	parser.add_argument("--feature", type=str, default='bert-10')
	parser.add_argument("--sessions", nargs='+', type=int, default=[1, 2, 3, 4, 5])
	parser.add_argument("--trim", type=int, default=5)
	parser.add_argument("--ndelays", type=int, default=4)
	parser.add_argument("--nboots", type=int, default=50)
	parser.add_argument("--chunklen", type=int, default=40)
	parser.add_argument("--nchunks", type=int, default=125)
	parser.add_argument("--singcutoff", type=float, default=1e-10)
	parser.add_argument("-use_corr", action="store_true")
	parser.add_argument("-single_alpha", action="store_true")
	logging.basicConfig(level=logging.INFO)


	args = parser.parse_args()
	globals().update(args.__dict__)

	fs = " ".join(_FEATURE_CONFIG.keys())
	assert args.feature in _FEATURE_CONFIG.keys(), "Available feature spaces:" + fs
	assert np.amax(args.sessions) <= 5 and np.amin(args.sessions) >=1, "1 <= session <= 5"
	train_stories, test_stories, allstories = encoding_utils.get_allstories(args.sessions)
	

	save_location = join(results_dir, args.feature, args.subject)
	print("Saving encoding model & results to:", save_location)
	os.makedirs(save_location, exist_ok=True)

	downsampled_feat = get_feature_space(args.feature, allstories)
	print("Stimulus & Response parameters:")
	print("trim: %d, ndelays: %d" % (args.trim, args.ndelays))

	# Delayed stimulus
	delRstim = encoding_utils.apply_zscore_and_hrf(train_stories, downsampled_feat, args.trim, args.ndelays)
	print("delRstim: ", delRstim.shape)
	delPstim = encoding_utils.apply_zscore_and_hrf(test_stories, downsampled_feat, args.trim, args.ndelays)
	print("delPstim: ", delPstim.shape)

	# Response
	zRresp = encoding_utils.get_response(train_stories, args.subject)
	print("zRresp: ", zRresp.shape)
	zPresp = encoding_utils.get_response(test_stories, args.subject)
	print("zPresp: ", zPresp.shape)

	# Ridge
	alphas = np.logspace(1, 3, 10)

	print("Ridge parameters:")
	print("nboots: %d, chunklen: %d, nchunks: %d, single_alpha: %s, use_corr: %s" % (
		args.nboots, args.chunklen, args.nchunks, args.single_alpha, args.use_corr))

	wt, corrs, valphas, bscorrs, valinds = bootstrap_ridge(
		delRstim, zRresp, delPstim, zPresp, alphas, args.nboots, args.chunklen, 
		args.nchunks, singcutoff=args.singcutoff, single_alpha=args.single_alpha, 
		use_corr=args.use_corr)

	# Save regression results.
	np.savez("%s/weights" % save_location, wt)
	np.savez("%s/corrs" % save_location, corrs)
	np.savez("%s/valphas" % save_location, valphas)
	np.savez("%s/bscorrs" % save_location, bscorrs)
	np.savez("%s/valinds" % save_location, np.array(valinds))
	print("Total r2: %d" % sum(corrs * np.abs(corrs)))
