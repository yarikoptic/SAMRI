# -*- coding: utf-8 -*-

from __future__ import print_function, division, unicode_literals, absolute_import
import csv
import os
import pandas as pd
# PyBIDS 0.6.5 and 0.10.2 compatibility
try:
	from bids.grabbids import BIDSLayout
except ModuleNotFoundError:
	from bids.layout import BIDSLayout
try:
	from bids.grabbids import BIDSValidator
except ModuleNotFoundError:
	from bids_validator import BIDSValidator
from copy import deepcopy
from datetime import datetime
from shutil import copyfile

GENERIC_PHASES = {
	"f_only_translation":{
		"transforms":"Translation",
		"transform_parameters":(0.1,),
		"number_of_iterations":[2000,1000,500],
		"metric":"MeanSquares",
		"metric_weight":1,
		"radius_or_number_of_bins":32,
		"sampling_strategy":"Regular",
		"sampling_percentage":0.8,
		"convergence_threshold":1.e-16,
		"convergence_window_size":20,
		"smoothing_sigmas":[2,1,0],
		"sigma_units":"vox",
		"shrink_factors":[4,2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"f_translation":{
		"transforms":"Translation",
		"transform_parameters":(0.1,),
		"number_of_iterations":[400,200],
		"metric":"MI",
		"metric_weight":1,
		"radius_or_number_of_bins":64,
		"sampling_strategy":"Regular",
		"sampling_percentage":0.8,
		"convergence_threshold":1.e-8,
		"convergence_window_size":20,
		"smoothing_sigmas":[1,0],
		"sigma_units":"vox",
		"shrink_factors":[2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"s_translation":{
		"transforms":"Translation",
		"transform_parameters":(0.1,),
		"number_of_iterations":[1000,500,500],
		"metric":"MeanSquares",
		"metric_weight":1,
		"radius_or_number_of_bins":32,
		"sampling_strategy":"Regular",
		"sampling_percentage":0.3,
		"convergence_threshold":1.e-16,
		"convergence_window_size":20,
		"smoothing_sigmas":[2,1,0],
		"sigma_units":"vox",
		"shrink_factors":[4,2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":False,
		},
	"similarity":{
		"transforms":"Similarity",
		"transform_parameters":(0.1,),
		"number_of_iterations":[1000],
		"metric":"MI",
		"metric_weight":1,
		"radius_or_number_of_bins":32,
		"sampling_strategy":'Regular',
		"sampling_percentage":0.75,
		"convergence_threshold":1.e-16,
		"convergence_window_size":10,
		"smoothing_sigmas":[0],
		"sigma_units":"vox",
		"shrink_factors":[1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"affine":{
		"transforms":"Affine",
		"transform_parameters":(0.05,),
		"number_of_iterations":[50],
		"metric":"MI",
		"metric_weight":1,
		"radius_or_number_of_bins":32,
		"sampling_strategy":'Regular',
		"sampling_percentage":0.66,
		"convergence_threshold":1.e-8,
		"convergence_window_size":10,
		"smoothing_sigmas":[0],
		"sigma_units":"vox",
		"shrink_factors":[1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"syn":{
		"transforms":"SyN",
		"transform_parameters":(0.05, 1.0, 15),
		"number_of_iterations":[50],
		"metric":["MI","CC"],
		#"metric":"MI",
		#"metric":"CC",
		"metric_weight":[0.25,0.75],
		#"metric_weight":1,
		"radius_or_number_of_bins":[32,5],
		#"radius_or_number_of_bins":16,
		#"radius_or_number_of_bins":4,
		"sampling_strategy":['Regular','Regular'],
		#"sampling_strategy":'Regular',
		"sampling_percentage":[0.8,0.8],
		#"sampling_percentage":0.8,
		"convergence_threshold":1.e-8,
		"convergence_window_size":10,
		"smoothing_sigmas":[0],
		"sigma_units":"vox",
		"shrink_factors":[1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":False,
		},
	}

TRANSFORM_PHASES = {
	"rigid":{
		"transforms":"Rigid",
		"transform_parameters":(0.1,),
		"number_of_iterations":[3000,3000,3000,3000],
		"metric":"GC",
		"metric_weight":1,
		"radius_or_number_of_bins":64,
		"sampling_strategy":"Regular",
		"sampling_percentage":0.2,
		"convergence_threshold":1.e-10,
		"convergence_window_size":20,
		"smoothing_sigmas":[3,2,1,0],
		"sigma_units":"vox",
		"shrink_factors":[8,4,2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"affine":{
		"transforms":"Affine",
		"transform_parameters":(0.1,),
		"number_of_iterations":[500,500,250],
		"metric":"MI",
		"metric_weight":1,
		"radius_or_number_of_bins":16,
		"sampling_strategy":None,
		"sampling_percentage":0.3,
		"convergence_threshold":1.e-16,
		"convergence_window_size":20,
		"smoothing_sigmas":[2,1,0],
		"sigma_units":"vox",
		"shrink_factors":[4,2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	"syn":{
		"transforms":"SyN",
		"transform_parameters":(0.1, 2.0, 0.2),
		"number_of_iterations":[500,500,500,250],
		"metric":"MI",
		"metric_weight":1,
		"radius_or_number_of_bins":16,
		"sampling_strategy":None,
		"sampling_percentage":0.3,
		"convergence_threshold":1.e-16,
		"convergence_window_size":20,
		"smoothing_sigmas":[3,2,1,0],
		"sigma_units":"vox",
		"shrink_factors":[8,4,2,1],
		#"use_estimate_learning_rate_once":False,
		"use_histogram_matching":True,
		},
	}

def bids_data_selection(base, structural_match, functional_match, subjects, sessions,
	verbose=False,
	joint_conditions=True,
	):
	"""
	Creates a Pandas Dataframe descriptor from a BIDS datapath, optionally filtering out conditions.

	Parameters
	----------

	base : str
		path specifying the root directory of the BIDS data
	structural_match : dict or bool
		Dictionary specifying a whitelist of BIDS field identifiers.
		False if no whitelist is specified.
	functional_match : dict or bool
		Dictionary specifying a whitelist of BIDS field identifiers.
		False if no whitelist is specified.
	subjects: list or bool
		A list of subjects which may be present in the 'subjects' column of the created Pandas DataFrame, 'df'.
		False if user does not want to filter DataFrame by subjects.
	sessions: list or bool
		A list of session names which may be present in the 'sessions' column of the created Pandas DataFrame, 'df'.
		False if user does not want to filter DataFrame by sessions.

	Returns
	-------

	df : pandas.DataFrame
		A Pandas DataFrame with information corresponding to the whitelisted BIDS identifiers and optionally filtered by subjects and/or sessions.
	"""
	validate = BIDSValidator()
	if verbose:
		for x in os.walk(base):
			print(x[0])
			if validate.is_bids(x[0]):
				print("Is not BIDS-formatted.")
			else:
				print("Detected!")
	#layout = BIDSLayout(base, validate=False, derivatives=True)
	layout = BIDSLayout(base,validate=False)
	try:
		df = layout.as_data_frame()
	except AttributeError:
		df = layout.to_df()

	# Not crashing if the run field is not present
	try:
		# Run is for some reason recorded as float
		df.loc[df['run'].notna(),'run'] = df.loc[df['run'].notnull(),'run'].apply(int).apply(str)
	except KeyError:
		pass

	# We should ignore dotdirs unless they're in the base path.
	df = df[~df.path.str.contains(base + ".*/\.")]

	if verbose:
		print(df)
		print(df.columns)
	# drop event files
	# PyBIDS 0.6.5 and 0.10.2 compatibility
	try:
		df = df[df.type != 'events']
	except AttributeError:
		df = df[df.suffix != 'events']

	# rm .json
	df = df.loc[df.path.str.contains('.nii')]

	# generate scan types for later
	df['scan_type'] = ""

	#print(df.path.str.startswith('task', beg=0,end=len('task')))
	beg = df.path.str.find('task-')
	end = df.path.str.find('.')
	#df.loc[df.modality == 'func', 'scan_type'] = 'acq-'+df['acq']+'_task-'+  df.path.str.partition('task-')[2].str.partition('.')[0]
	#df.loc[df.modality == 'anat', 'scan_type'] = 'acq-'+df['acq']+'_' + df['type']
	#TODO: fix task!=type
	if 'func' in df.columns:
		df.loc[df.modality == 'func', 'task'] = df.path.str.partition('task-')[2].str.partition('_')[0]
		df.loc[df.modality == 'func', 'scan_type'] = 'task-' + df['task'] + '_acq-'+ df['acq']
	if 'anat' in df.columns:
		df.loc[df.modality == 'anat', 'scan_type'] = 'acq-'+df['acq'] +'_' + df['type']

	# Unclear in current BIDS specification, we refer to BOLD/CBV as modalities and func/anat as types
	# Can be removed after Pybids 0.10.2 migration
	df = df.rename(columns={'modality': 'type', 'type': 'modality'})

	#TODO: The following should be collapsed into one criterion category
	if functional_match or structural_match:
		res_df = pd.DataFrame()
		if functional_match:
			_df = deepcopy(df)
			try:
				if joint_conditions:
					for match in functional_match.keys():
						_df = _df.loc[_df[match].isin(functional_match[match])]
					res_df = res_df.append(_df)
				else:
					for match in functional_match.keys():
						_df = filter_data(_df, match, functional_match[match])
						res_df = res_df.append(_df)
			except:
				pass
		if structural_match:
			_df = deepcopy(df)
			try:
				if joint_conditions:
					for match in structural_match.keys():
						_df = _df.loc[_df[match].isin(structural_match[match])]
					res_df = res_df.append(_df)
				else:
					for match in structural_match.keys():
						_df = filter_data(_df, match, structural_match[match])
						res_df = res_df.append(_df)
			except:
				pass
		df = res_df

	if subjects:
		df = filter_data(df, 'subject', subjects)
	if sessions:
		df = filter_data(df, 'session', sessions)

	return df

def filter_data(df, col_name, entries):
	"""Filter a Pandas DataFrame if the `col_name` entry corresponds to any item in the `entries` list.

	Parameters
	----------

	df : pandas.DataFrame
		A Pandas DataFrame with a column name corresponding to the value of `col_name`.
	col_name : str
		The name of a column in `df`.
	entries : list
		A list of values which may be present on the `col_name` column of the `df` DataFrame.

	Returns
	-------
	pandas.DataFrame
		A filtered Pandas DataFrame.
	"""
	res_df = pd.DataFrame()
	in_df = df[col_name].dropna().unique().tolist()
	for entry in entries:
		if(entry in in_df):
			_df = df[df[col_name] == entry]
			res_df = res_df.append(_df)
	return res_df

def parse_paravision_date(pv_date):
	"""Convert ParaVision-style datetime string to Python datetime object.

	Parameters
	----------

	pv_date : str
		ParaVision datetime string.

	Returns
	-------

	`datetime.datetime` : A Python datetime object.

	Notes
	-----

	The datetime object produced does not contain a timezone, and should therefor only be used to determine time deltas relative to other datetimes from the same session.
	"""
	from datetime import datetime

	try:
		pv_date, _ = pv_date.rsplit('+',1)
	except ValueError:
		pv_date, _ = pv_date.rsplit('-',1)
	pv_date += "000"
	pv_date = datetime.strptime(pv_date, "%Y-%m-%dT%H:%M:%S,%f")
	return pv_date

def fslmaths_invert_values(img_path):
	"""Calculates the op_string required to make an fsl.ImageMaths() node invert an image"""
	op_string = "-sub {0} -sub {0}".format(img_path)
	return op_string

def iterfield_selector(iterfields, selector, action):
	"""Include or exclude entries from iterfields based on a selector dictionary

	Parameters
	----------

	iterfields : list
	A list of lists (or tuples) containing entries fromatted at (subject_id,session_id,task_id)

	selector : dict
	A dictionary with any combination of "sessions", "subjects", "tasks" as keys and corresponding identifiers as values.

	action : "exclude" or "include"
	Whether to exclude or include (and exclude all the other) matching entries from the output.
	"""
	name_map = {"subjects": 0, "sessions": 1, "tasks":2}
	keep = []
	for ix, iterfield in enumerate(iterfields):
		for key in selector:
			selector[key] = [str(i) for i in selector[key]]
			if iterfield[name_map[key]] in selector[key]:
				keep.append(ix)
				break
	if action == "exclude":
		iterfields = [iterfields[i] for i in range(len(iterfields)) if i not in keep]
	elif action == "include":
		iterfields = [iterfields[i] for i in keep]
	return iterfields

def datasource_exclude(in_files, excludes, output="files"):
	"""Exclude file names from a list that match a BIDS-style specifications from a dictionary.

	Parameters
	----------

	in_files : list
	A list of flie names.

	excludes : dictionary
	A dictionary with keys which are "subjects", "sessions", or "scans", and values which are lists giving the subject, session, or scan identifier respectively.

	output : string
	Either "files" or "len". The former outputs the filtered file names, the latter the length of the resulting list.
	"""

	if not excludes:
		out_files = in_files
	else:
		exclude_criteria=[]
		for key in excludes:
			if key in "subjects":
				for i in excludes[key]:
					exclude_criteria.append("sub-"+str(i))
			if key in "sessions":
				for i in excludes[key]:
					exclude_criteria.append("ses-"+str(i))
			if key in "scans":
				for i in excludes[key]:
					exclude_criteria.append("task-"+str(i))
		out_files = [in_file for in_file in in_files if not any(criterion in in_file for criterion in exclude_criteria)]
	if output == "files":
		return out_files
	elif output == "len":
		return len(out_files)


def bids_dict_to_dir(bids_dictionary):
	"""Concatenate a (subject, session) or (subject, session, scan) tuple to a BIDS-style path"""
	subject = "sub-" + bids_dictionary['subject']
	session = "ses-" + bids_dictionary['session']
	return "/".join([subject,session])

def ss_to_path(subject_session):
	"""Concatenate a (subject, session) or (subject, session, scan) tuple to a BIDS-style path"""
	subject = "sub-" + subject_session[0]
	session = "ses-" + subject_session[1]
	return "/".join([subject,session])

def bids_dict_to_source(bids_dictionary, source_format):
	"""Generate a string from the source format with inserted corresponding values from the given dictionary.

	Parameters
	----------

	bids_dictionary : dict
		A dictionary with keys that are BIDS identifiers.
	source_format : str
		A Python format string with identifiers which are keys of the bids_dictionary parameter.
	"""
	from os import path

	source = source_format.format(**bids_dictionary)

	return source

def out_path(selection_df, in_path,
	in_field='path',
	out_field='out_path',
	):
	"""Select the `out_path` field corresponding to a given `in_path` from a BIDS-style selection dataframe which includes an `out_path` column.
	"""

	out_path = selection_df[selection_df[in_field]==in_path][out_field].item()

	return out_path

def container(selection_df, out_path,
	kind='',
	out_field='out_path',
	):

	subject = selection_df[selection_df[out_field]==out_path]['subject'].item()
	session = selection_df[selection_df[out_field]==out_path]['session'].item()

	container = 'sub-{}/ses-{}'.format(subject,session)
	if kind:
		container += '/'
		container += kind

	return container

def bids_naming(subject_session, metadata,
	extra=['acq'],
	extension='.nii.gz',
	suffix='',
	):
	"""
	Generate a BIDS filename from a subject-and-session iterator, a scan type, and a `pandas.DataFrame` metadata container.

	Parameters
	----------

	subject_session : tuple
		Length-2 tuple containing two strings, of which the first denotes the subject and the second the session.
	metadata : pandas.DataFrame
		Pandas Dataframe object containing columns named 'subject', and 'session'.
	"""
	subject, session = subject_session
	filename = 'sub-{}'.format(subject)
	filename += '_ses-{}'.format(session)
	selection =  metadata.loc[(metadata['subject']==subject)&(metadata['session']==session)]

	if selection.empty:
		return
	try:
		task = selection['task']
	except KeyError:
		pass
	else:
		if not task.isnull().all():
			task = task.item()
			filename += '_task-{}'.format(task)
	if 'acq' in extra:
		acq = selection['acquisition']
		if not acq.isnull().all():
			acq = acq.item()
			filename += '_acq-{}'.format(acq)
	if 'run' in extra:
		acq = selection['run']
		if not acq.isnull().all():
			acq = acq.item()
			filename += '_run-{}'.format(acq)
	if not suffix:
		try:
			modality = selection['modality']
		except KeyError:
			pass
		else:
			if not modality.isnull().all():
				modality = modality.item()
				filename += '_{}'.format(modality)
	else:
		filename += '_{}'.format(suffix)
	filename += extension

	return filename

def sss_filename(subject_session, scan, scan_prefix="task", suffix="", extension=".nii.gz"):
	"""Concatenate subject-condition and scan inputs to a BIDS-style filename

	Parameters
	----------

	subject_session : list
	Length-2 list of subject and session identifiers

	scan : string
	Scan identifier

	suffix : string, optional
	Measurement type suffix (commonly "bold" or "cbv")
	"""
	# we do not want to modify the subject_session iterator entry
	from copy import deepcopy
	subject_session = deepcopy(subject_session)

	subject_session[0] = "sub-" + subject_session[0]
	subject_session[1] = "ses-" + subject_session[1]
	if suffix:
		suffix = "_"+suffix
	if scan_prefix:
		scan = "".join([scan_prefix,"-",scan,suffix,extension])
	else:
		scan = "".join([scan,suffix,extension])
	subject_session.append(scan)
	return "_".join(subject_session)

def select_template(template, registration_mask):
	"""Select the template and mask to be used, this supports special string values which select default SAMRI settings"""
	if template:
		if template == "mouse":
			template = '/usr/share/mouse-brain-templates/dsurqec_200micron.nii'
			registration_mask = '/usr/share/mouse-brain-templates/dsurqec_200micron_mask.nii'
		elif template == "rat":
			from samri.fetch.templates import fetch_rat_waxholm
			template = fetch_rat_waxholm()['template']
			registration_mask = fetch_rat_waxholm()['mask']
		else:
			if template:
				template = path.abspath(path.expanduser(template))
			if registration_mask:
				registration_mask = path.abspath(path.expanduser(registration_mask))
	else:
		raise ValueError("No species or template path specified")
		return -1

	return template, registration_mask

def sessions_file(out_dir, df,
	):
	"""Create new sessions file for a particular subject, given the BIDS guidelines.
	https://bids-specification.readthedocs.io/en/latest/05-longitudinal-and-multi-site-studies.html#sessions-file

	Parameters
	----------

	out_dir : str
		Path to output root.
	df : pandas.DataFrame
		Pandas Dataframe containing columns including 'measurement', 'session', and 'subject'.
	"""

	import numpy as np

	for sub_dir in os.listdir(out_dir):
		sub_path = os.path.join(out_dir,sub_dir)
		if os.path.isdir(sub_path) and sub_dir[:4] == 'sub-':
			if os.path.isfile(os.path.join(sub_path,'{}_sessions.tsv'.format(sub_dir))):
				continue
			sessions_data=[]
			for ses_dir in os.listdir(sub_path):
				d={}
				if os.path.isdir(os.path.join(out_dir,sub_dir,ses_dir)) and ses_dir[:4] == 'ses-':
					acq_time = df.loc[(df['subject'] == sub_dir[4:]) & (df['session'] == ses_dir[4:]),'measurement'].tolist()[0]
					acq_time = os.path.basename(acq_time)
					acq_time = acq_time.split('_')[:2]
					acq_time = '_'.join(acq_time)
					try:
						acq_time = datetime.strptime(acq_time, '%Y%m%d_%H%M%S')
					except ValueError:
						d['acq_time'] = np.nan
					else:
						d['session_id'] = ses_dir
						d['acq_time'] = acq_time.isoformat()
					sessions_data.append(d)
			keys = sessions_data[0].keys()
			with open(os.path.join(sub_path,'{}_sessions.tsv'.format(sub_dir)), "w+") as f:
				dict_writer = csv.DictWriter(f, keys, delimiter='\t')
				dict_writer.writeheader()
				dict_writer.writerows(sessions_data)

def copy_bids_files(bids_in, bids_out):
	"""Copy BIDS metadata files.

	Parameters
	----------

	bids_in : str
		Input BIDS data directory.
	out_out : str
		Output BIDS data directory.
	"""

	bids_file_list = [
		'participants.tsv',
		'participants.json',
		'dataset_description.json',
		]
	for i in bids_file_list:
		in_file = os.path.join(bids_in,i)
		out_file = os.path.join(bids_out,i)
		try:
			copyfile(in_file,out_file)
		except:
			pass
