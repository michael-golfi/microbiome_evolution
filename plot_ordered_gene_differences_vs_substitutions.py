import matplotlib  
matplotlib.use('Agg') 
import parse_midas_data
import pylab
import sys
import numpy
import diversity_utils
import stats_utils
import matplotlib.colors as colors
import matplotlib.cm as cmx
from math import log10,ceil
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

mpl.rcParams['font.size'] = 6
mpl.rcParams['lines.linewidth'] = 0.5
mpl.rcParams['legend.frameon']  = False
mpl.rcParams['legend.fontsize']  = 'small'


################################################################################
#
# Standard header to read in argument information
#
################################################################################
if len(sys.argv)>1:
    if len(sys.argv)>2:
        debug=True # debug does nothing in this script
        species_name=sys.argv[2]
    else:
        debug=False
        species_name=sys.argv[1]
else:
    sys.stderr.write("Usage: python command.py [debug] species_name")
################################################################################

min_change = 0.8
min_coverage = 20


# Load subject and sample metadata
sys.stderr.write("Loading HMP metadata...\n")
subject_sample_map = parse_midas_data.parse_subject_sample_map()
sys.stderr.write("Done!\n")
    
# Load genomic coverage distributions
sample_coverage_histograms, samples = parse_midas_data.parse_coverage_distribution(species_name)
median_coverages = numpy.array([stats_utils.calculate_nonzero_median_from_histogram(sample_coverage_histogram) for sample_coverage_histogram in sample_coverage_histograms])
sample_coverage_map = {samples[i]: median_coverages[i] for i in xrange(0,len(samples))}
    
# Load SNP information for species_name
sys.stderr.write("Loading SNP data for %s...\n" % species_name)
snp_samples, allele_counts_map, passed_sites_map = parse_midas_data.parse_snps(species_name, debug)
sys.stderr.write("Done!\n")
 
median_coverages = numpy.array([sample_coverage_map[snp_samples[i]] for i in xrange(0,len(snp_samples))])
  
# Calculate full matrix of synonymous pairwise differences
sys.stderr.write("Calculate synonymous pi matrix...\n")
pi_matrix_syn, avg_pi_matrix_syn = diversity_utils.calculate_pi_matrix(allele_counts_map, passed_sites_map, variant_type='4D')
pi_matrix_syn = numpy.clip(pi_matrix_syn,1e-06,1)
avg_pi_matrix_syn = numpy.clip(avg_pi_matrix_syn,1e-06,1)
pis = numpy.diag(pi_matrix_syn)
sys.stderr.write("Done!\n")

# Calculate fixation matrix
sys.stderr.write("Calculate matrix of snp differences...\n")
snp_difference_matrix, snp_opportunity_matrix = diversity_utils.calculate_fixation_matrix(allele_counts_map, passed_sites_map, min_change=min_change)    
sys.stderr.write("Done!\n")
   
# Load gene presence/absence information for species_name
sys.stderr.write("Loading pangenome data for %s...\n" % species_name)
gene_samples, gene_names, gene_presence_matrix, gene_depth_matrix, marker_coverages, gene_reads_matrix = parse_midas_data.parse_pangenome_data(species_name)
sys.stderr.write("Done!\n")
        
# Calculate matrix of number of genes that differ
sys.stderr.write("Calculating matrix of gene differences...\n")
gene_difference_matrix, gene_opportunity_matrix = diversity_utils.calculate_coverage_based_gene_hamming_matrix(gene_depth_matrix, marker_coverages, min_log2_fold_change=4)

# Now need to make the gene samples and snp samples match up
desired_samples = list(set(snp_samples[(median_coverages>=min_coverage)*(pis<1e-03)]) & set(gene_samples[marker_coverages>min_coverage]))   
     
# Calculate which pairs of idxs belong to the same sample, which to the same subject
# and which to different subjects
desired_same_sample_idxs, desired_same_subject_idxs, desired_diff_subject_idxs = parse_midas_data.calculate_subject_pairs(subject_sample_map, desired_samples)

snp_sample_idx_map = parse_midas_data.calculate_sample_idx_map(desired_samples, snp_samples)
gene_sample_idx_map = parse_midas_data.calculate_sample_idx_map(desired_samples, gene_samples)
    

same_sample_snp_idxs  = parse_midas_data.apply_sample_index_map_to_indices(snp_sample_idx_map,  desired_same_sample_idxs)  
same_sample_gene_idxs = parse_midas_data.apply_sample_index_map_to_indices(gene_sample_idx_map, desired_same_sample_idxs)  


same_subject_snp_idxs = parse_midas_data.apply_sample_index_map_to_indices(snp_sample_idx_map, desired_same_subject_idxs)  
same_subject_gene_idxs = parse_midas_data.apply_sample_index_map_to_indices(gene_sample_idx_map, desired_same_subject_idxs)  

diff_subject_snp_idxs = parse_midas_data.apply_sample_index_map_to_indices(snp_sample_idx_map, desired_diff_subject_idxs)  
diff_subject_gene_idxs = parse_midas_data.apply_sample_index_map_to_indices(gene_sample_idx_map, desired_diff_subject_idxs)  


same_subject_snp_plowers = []
same_subject_snp_puppers = []
same_subject_gene_plowers = []
same_subject_gene_puppers = []
for sample_pair_idx in xrange(0,len(same_subject_snp_idxs[0])):
    
    i = same_subject_snp_idxs[0][sample_pair_idx]
    j = same_subject_snp_idxs[1][sample_pair_idx]
    
    plower,pupper = stats_utils.calculate_poisson_rate_interval(snp_difference_matrix[i,j], snp_opportunity_matrix[i,j])
    
    same_subject_snp_plowers.append(plower)
    same_subject_snp_puppers.append(pupper)
    
    snp_differences = diversity_utils.calculate_snp_differences_between(i,j,allele_counts_map, passed_sites_map, min_change=min_change)

    i = same_subject_gene_idxs[0][sample_pair_idx]
    j = same_subject_gene_idxs[1][sample_pair_idx]
    gene_differences = diversity_utils.calculate_gene_differences_between(i, j, gene_names, gene_depth_matrix, marker_coverages, min_log2_fold_change=4)

    plower,pupper = stats_utils.calculate_poisson_rate_interval(gene_difference_matrix[i,j], gene_opportunity_matrix[i,j])
    
    same_subject_gene_plowers.append(plower)
    same_subject_gene_puppers.append(pupper)
   

    if (len(snp_differences)>0) or (len(gene_differences)>0):
        # Print them out!
        print "Changes between pair", sample_pair_idx
        print "SNPs:"
        if len(snp_differences)>0:
            for snp_diff_idx in xrange(0,len(snp_differences)):
                print snp_differences[snp_diff_idx]
        print "Genes:"
        if len(gene_differences)>0:
            for gene_diff_idx in xrange(0,len(gene_differences)):
                print gene_differences[gene_diff_idx]
        
    else:
        pass


# Sort all four lists by ascending upper bound on SNP changes
same_subject_snp_puppers, same_subject_snp_plowers, same_subject_gene_puppers, same_subject_gene_plowers = (numpy.array(x) for x in zip(*sorted(zip(same_subject_snp_puppers, same_subject_snp_plowers, same_subject_gene_puppers, same_subject_gene_plowers))))
# clip lower bounds 
same_subject_gene_plowers = numpy.clip(same_subject_gene_plowers,1e-09,1e09)
same_subject_snp_plowers = numpy.clip(same_subject_snp_plowers,1e-09,1e09)

diff_subject_snp_plowers = []
diff_subject_snp_puppers = []
diff_subject_gene_plowers = []
diff_subject_gene_puppers = []
for sample_pair_idx in xrange(0,len(diff_subject_snp_idxs[0])):
    
    i = diff_subject_snp_idxs[0][sample_pair_idx]
    j = diff_subject_snp_idxs[1][sample_pair_idx]
    
    plower,pupper = stats_utils.calculate_poisson_rate_interval(snp_difference_matrix[i,j], snp_opportunity_matrix[i,j])
    
    diff_subject_snp_plowers.append(plower)
    diff_subject_snp_puppers.append(pupper)
    
    
    i = diff_subject_gene_idxs[0][sample_pair_idx]
    j = diff_subject_gene_idxs[1][sample_pair_idx]
    gene_differences = diversity_utils.calculate_gene_differences_between(i, j, gene_names, gene_depth_matrix, marker_coverages, min_log2_fold_change=4)

    plower,pupper = stats_utils.calculate_poisson_rate_interval(gene_difference_matrix[i,j], gene_opportunity_matrix[i,j])
    
    diff_subject_gene_plowers.append(plower)
    diff_subject_gene_puppers.append(pupper)

# Sort all four lists by ascending upper bound on SNP changes
diff_subject_snp_puppers, diff_subject_snp_plowers, diff_subject_gene_puppers, diff_subject_gene_plowers = (numpy.array(x) for x in zip(*sorted(zip(diff_subject_snp_puppers, diff_subject_snp_plowers, diff_subject_gene_puppers, diff_subject_gene_plowers))))

# clip lower bounds 
diff_subject_gene_plowers = numpy.clip(diff_subject_gene_plowers,1e-09,1e09)
diff_subject_snp_plowers = numpy.clip(diff_subject_snp_plowers,1e-09,1e09)

# Done calculating... now plot figure!

total_num_pairs = len(same_subject_snp_plowers)+len(diff_subject_snp_plowers)
print total_num_pairs

total_height = total_num_pairs/300.0*4

# Set up figure
fig = plt.figure(figsize=(5, total_height))

# Set up grids to hold figure panels
outer_grid = gridspec.GridSpec(1, 2, width_ratios=[1,1], wspace=0.05)

###################
#
# SNP Panel
#
###################

snp_axis = plt.Subplot(fig, outer_grid[0])
fig.add_subplot(snp_axis)

snp_axis.set_ylabel('Sample pairs')
snp_axis.set_xlabel('Substitution rate')
snp_axis.set_xlim([1e-06,1e-01])

snp_axis.semilogx([1e-09,1e-09],[1,1],'g-',label='Within host')
snp_axis.semilogx([1e-09,1e-09],[1,1],'r-',label='Between host')

###################
#
# Gene Panel
#
###################

gene_axis = plt.Subplot(fig, outer_grid[1])
fig.add_subplot(gene_axis)

gene_axis.set_xlabel('Gene gain/loss rate')
gene_axis.set_xlim([2e-05,1])

y = 0
for snp_plower, snp_pupper, gene_plower, gene_pupper in zip(same_subject_snp_plowers, same_subject_snp_puppers, same_subject_gene_plowers, same_subject_gene_puppers):

    y-=1
    
    snp_axis.semilogx([snp_plower,snp_pupper],[y,y],'g-',linewidth=0.35)
    gene_axis.semilogx([gene_plower,gene_pupper],[y,y],'g-',linewidth=0.35)
    
for snp_plower, snp_pupper, gene_plower, gene_pupper in zip(diff_subject_snp_plowers, diff_subject_snp_puppers, diff_subject_gene_plowers, diff_subject_gene_puppers):

    y-=1
    
    snp_axis.semilogx([snp_plower,snp_pupper],[y,y],'r-',linewidth=0.35)
    gene_axis.semilogx([gene_plower,gene_pupper],[y,y],'r-',linewidth=0.35)

snp_axis.set_ylim([y-1,0])
gene_axis.set_ylim([y-1,0])    

snp_axis.set_yticks([])
gene_axis.set_yticks([])

snp_axis.legend(loc='lower left',frameon=False)

fig.savefig('%s/%s_ordered_gene_differences_vs_substitutions.pdf' % (parse_midas_data.analysis_directory,species_name),bbox_inches='tight')
fig.savefig('%s/%s_ordered_gene_differences_vs_substitutions.png' % (parse_midas_data.analysis_directory,species_name),bbox_inches='tight',dpi=300)

    
