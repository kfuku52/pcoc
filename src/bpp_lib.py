#  bpp_lib.py
#
#  Copyright 2017 Carine Rey <carine.rey@ens-lyon.fr>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

#import subprocess
import commands
import os
import sys,re

import logging
logger = logging.getLogger("pcoc.bpp_lib")

import pandas as pd

debug_mode_bpp = False

########################################################################
##                    Functions                                       ##
########################################################################

def write_global_config(d, estim=True, sim_profiles_name=""):
    bpp_config_files_estim = [
                   ("CATseq_estim.bpp", CATseq_estim),
                   ("CATseq_conv.bpp", CATseq_conv_bpp)]
    bpp_config_files_sim = [("CATseq_sim.bpp", CATseq_sim_bpp)]

    files_list = bpp_config_files_sim
    if estim:
        files_list.extend(bpp_config_files_estim)

    if sim_profiles_name == "C10":
        files_list.append(("CATC10Distances.csv", CATC10Distances))
    elif sim_profiles_name == "C60":
        files_list.append(("CATC60Distances.csv", CATC60Distances))

    for (f, s) in files_list:

        with open(d+"/"+f, "w") as F:
            F.write(s)


########################################################################
##                    BPP simulations                                 ##
########################################################################

def make_simul(name, c1, c2, g_tree, sim_profiles,
               number_of_sites=1000,
               outputInternalSequences="yes",
               cz_nodes={}, CzOneChange=True):

    nodesWithAncestralModel  = g_tree.conv_events.nodesWithAncestralModel_sim
    nodesWithTransitions     = g_tree.conv_events.nodesWithTransitions_sim
    nodesWithConvergentModel = g_tree.conv_events.nodesWithConvergentModel_sim
    repseq                   = g_tree.repseq
    repbppconfig             = g_tree.repbppconfig
    tree_fn                  = g_tree.tree_fn_sim
    cz_nodes                 = g_tree.cz_nodes

    if not os.path.isfile(tree_fn):
        logger.error("%s is not a file", tree_fn)

    fasta_outfile = "%s/%s%s" %(repseq.replace("//","/"), name, ".fa")


    if outputInternalSequences != "yes":
        outputInternalSequences = "no"

    number_of_models = 0

    command="bppseqgen output.sequence.file=%s \'rate_distribution=Gamma(n=4)\' input.tree.file=%s number_of_sites=%s output.internal.sequences=%s " %(fasta_outfile, tree_fn, number_of_sites, outputInternalSequences)

    if sim_profiles.name in ["C10","C60"]:
        command += " NBCAT=%s " %(sim_profiles.nb_cat)
    else:
        if not os.path.isfile(sim_profiles.formatted_frequencies_filename):
            logger.error("%s is not a file", sim_profiles.formatted_frequencies_filename)
        command += " PROFILE_F=%s " %(sim_profiles.formatted_frequencies_filename)
    
    command+=" param=%s.bpp Ne1=%d Ne2=%d " %(repbppconfig+"/CATseq_sim",c1,c2)

    if sim_profiles.name in ["C10","C60"]:
        command+=" modelA=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c1)
        command+=" modelC=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c2)
        command+=" modelOC=\'OneChange(model=$(modelC))\' "
    else:
        command+=" modelA=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne1)))\' "
        command+=" modelC=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne2)))\' "
        command+=" modelOC=\'OneChange(model=$(modelC))\' "


    command += " \'nonhomogeneous.root_freq=FromModel(model=$(modelA))\' "

    if c1!=c2:
        if nodesWithAncestralModel:
            number_of_models +=1
            command+=" model%s=\'$(modelA)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithAncestralModel)))

        if nodesWithTransitions:
            number_of_models +=1
            command+=" model%s=\'$(modelOC)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithTransitions)))

        if nodesWithConvergentModel:
            number_of_models +=1
            command+=" model%s=\'$(modelC)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithConvergentModel)))

    else:
        allNodes = nodesWithConvergentModel+nodesWithTransitions+nodesWithAncestralModel
        number_of_models +=1
        command+=" model%s=\'$(modelA)\' " %(number_of_models)
        command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, allNodes)))

    # If noisy profiles
    sup_command = ""
    if cz_nodes:
        for (cz, nodes) in cz_nodes.items():
            if nodes:
                if CzOneChange:
                    number_of_models +=1
                    if sim_profiles.name in ["C10","C60"]:
                        sup_command+=" model%s=\'OneChange(model=LGL08_CAT_C%s(nbCat=$(NBCAT)))\' " %(number_of_models, cz)
                    else:
                        sup_command+=" model%s=\'OneChange(model=LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=%s)))\' " %(number_of_models, cz)
                    t_node = nodes[0]
                    sup_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,str(t_node))
                    if len(nodes) > 1:
                        number_of_models +=1
                        if sim_profiles.name in ["C10","C60"]:
                            sup_command+=" model%s=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(number_of_models, cz)
                        else:
                            sup_command+=" model%s=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=%s))\' " %(number_of_models, cz)
                        sup_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str,nodes[1:])))
                else:
                    number_of_models +=1
                    if sim_profiles.name in ["C10","C60"]:
                        sup_command+=" model%s=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(number_of_models, cz)
                    else:
                        sup_command+=" model%s=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=%s))\' " %(number_of_models, cz)
                    sup_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodes)))

    command+=sup_command + " nonhomogeneous.number_of_models=%s " %(number_of_models)

    out = commands.getoutput(command)

    if debug_mode_bpp:
        logger.info("%s\n%s\n%s", command, out, command)


########################################################################
##                    BPP estimations                                 ##
########################################################################

def make_estim(name, c1, c2, g_tree, est_profiles, suffix="",
               OneChange=True, ext=".fa", gamma=False,
               max_gap_allowed=90, inv_gamma=False):

    nodesWithAncestralModel  = g_tree.conv_events.nodesWithAncestralModel_est
    nodesWithTransitions     = g_tree.conv_events.nodesWithTransitions_est
    nodesWithConvergentModel = g_tree.conv_events.nodesWithConvergentModel_est
    tree_fn                  = g_tree.tree_fn_est
    repseq                   = g_tree.repseq
    repest                   = g_tree.repest
    repbppconfig             = g_tree.repbppconfig

    fasta_file = "%s/%s%s" %(repseq, name, ext)
    #logger.debug("fasta_file: %s",fasta_file )

    if not os.path.isfile(tree_fn):
        logger.error("%s is not a file", tree_fn)
    if not os.path.isfile(fasta_file):
        logger.error("%s is not a file", fasta_file)

    output_infos =  "%s/%s_%s_%s%s.infos"  %(repest, name , c1, c2, suffix)
    output_params = "%s/%s_%s_%s%s.params" %(repest, name , c1, c2, suffix)

    command = "bppml param=%s \'optimization.ignore_parameters=*\' output.infos=%s output.estimates=%s input.tree.file=%s \'input.sequence.file=%s\' " %(repbppconfig+"/CATseq_estim.bpp", output_infos, output_params, tree_fn, fasta_file)
    number_of_models = 0

    if est_profiles.name in ["C10","C60"]:
        command += " NBCAT=%s " %(est_profiles.nb_cat)
    else:
        if not os.path.isfile(est_profiles.formatted_frequencies_filename):
            logger.error("%s is not a file", est_profiles.formatted_frequencies_filename)
        command += " PROFILE_F=%s " %(est_profiles.formatted_frequencies_filename)


    command += "Ne1=%d Ne2=%d" %(c1, c2)
    if est_profiles.name in ["C10","C60"]:
        command+=" modelA=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c1)
        command+=" modelC=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c2)
        command+=" modelOC=\'OneChange(model=$(modelC))\' "
    else:
        command+=" modelA=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne1)))\' "
        command+=" modelC=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne2)))\' "
        command+=" modelOC=\'OneChange(model=$(modelC))\' "

    command += " \'nonhomogeneous.root_freq=FromModel(model=$(modelA))\' "

    if nodesWithAncestralModel:
        number_of_models +=1
        command+=" model%s=\'$(modelA)\' " %(number_of_models)
        command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithAncestralModel)))

    if OneChange:
        if nodesWithConvergentModel:
            number_of_models +=1
            command+=" \'model%s=$(modelC)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithConvergentModel)))

        if nodesWithTransitions:
            number_of_models +=1
            # Mixture
            command+=" \'model%s=$(modelOC)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithTransitions)))

    else:
        nodesWithTransitionsAndWithConvergentModel = nodesWithTransitions+nodesWithConvergentModel
        if nodesWithTransitionsAndWithConvergentModel:
            number_of_models +=1
            command+=" model%s=\'$(modelC)\' " %(number_of_models)
            command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithTransitionsAndWithConvergentModel)))

    if gamma:
        command+=" rate_distribution=\'Gamma(n=4)\' "
    elif inv_gamma:
        command+=" rate_distribution=\'Invariant(dist=Gamma(n=4))\' "
    else:
        command+=" rate_distribution=\'Constant()\' "

    if 0 <= max_gap_allowed <=100:
        command+=" input.sequence.max_gap_allowed=%s " %(max_gap_allowed)
    else:
        logger.error("max_gap_allowed (%s) must be between 0 and 100", max_gap_allowed)
        sys.error(1)

    command += "nonhomogeneous.number_of_models=%s " %(number_of_models)

    if debug_mode_bpp:
        logger.debug("%s", command)

    out = commands.getoutput(command)

    if debug_mode_bpp:
        logger.info("%s\n%s", out, command)

    if re.search("^Number of sites retained.*: 0$",out,re.MULTILINE) or \
        re.search("^Number of sites.*: 0$",out,re.MULTILINE):
        logger.warning("No site retained for %s (too much gaps), you can use the \"--max_gap_allowed\" option.", name)
        f_infos = open(output_infos,"w")
        f_infos.close()

    if not os.path.exists(output_infos):
        logger.error("%s does not exist", output_infos)
        logger.error("command: %s\nout:\n%s", command, out)
        sys.exit(42)
        
    ### Read outputs ###
    logger.info("Read and save likelihoods (%s, %s)", c1, c2)
    ## bppml ##
    df_bppml = pd.read_csv(output_infos, sep = '\s+', names = ["Sites", "is.complete", "is.constant", "lnl", "rc", "pr"], header = 0)
    logger.debug("bppml: %s", df_bppml.to_string() )
    
    df_bppml = df_bppml[["Sites", "lnl"]]
    df_bppml["C1"] = c1
    df_bppml["C2"] = c2
    df_bppml["OneChange"] = OneChange
    df_bppml["T_C1"] = None
    df_bppml["T_C2"] = None
    df_bppml["Sites"] = df_bppml["Sites"].str.replace("[","").str.replace("]","")
    df_bppml[["Sites", "lnl"]]
    df_bppml["Sites"] = pd.to_numeric(df_bppml["Sites"])
    
    return(df_bppml)

def make_estim_mixture(name, c1, c2, g_tree, est_profiles, suffix="",
               ext=".fa", gamma=False,
               max_gap_allowed=90, inv_gamma=False):

    nodesWithAncestralModel  = g_tree.conv_events.nodesWithAncestralModel_est
    nodesWithTransitions     = g_tree.conv_events.nodesWithTransitions_est
    nodesWithConvergentModel = g_tree.conv_events.nodesWithConvergentModel_est
    tree_fn                  = g_tree.tree_fn_est
    repseq                   = g_tree.repseq
    repest                   = g_tree.repest
    repbppconfig             = g_tree.repbppconfig

    fasta_fn = "%s/%s%s" %(repseq, name, ext)

    if not os.path.isfile(tree_fn):
        logger.error("%s is not a file", tree_fn)
    if not os.path.isfile(fasta_fn):
        logger.error("%s is not a file", fasta_fn)
    
    
    ### BPPML ###
    output_infos_bppml =  "%s/%s_%s_%s%s.infos"  %(repest, name , c1, c2, suffix)
    output_params_bppml = "%s/%s_%s_%s%s.params" %(repest, name , c1, c2, suffix)

    bppml_command  = "bppml param=%s " %(repbppconfig+"/CATseq_estim.bpp")
    bppml_command += " \'optimization.ignore_parameters=BrLen*,Mixture.relrate*\' "
    bppml_command += " output.infos=%s output.estimates=%s "       %(output_infos_bppml, output_params_bppml)
    bppml_command += " input.tree.file=%s input.sequence.file=%s " %(tree_fn, fasta_fn)
    number_of_models = 0

    if est_profiles.name in ["C10","C60"]:
        bppml_command += " NBCAT=%s " %(est_profiles.nb_cat)
    else:
        if not os.path.isfile(est_profiles.formatted_frequencies_filename):
            logger.error("%s is not a file", est_profiles.formatted_frequencies_filename)
        bppml_command += " PROFILE_F=%s " %(est_profiles.formatted_frequencies_filename)


    bppml_command += "Ne1=%d Ne2=%d" %(c1, c2)
    if est_profiles.name in ["C10","C60"]:
        bppml_command+=" modelA=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c1)
        bppml_command+=" modelC=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c2)
        bppml_command+=" modelOC=\'OneChange(model=$(modelC))\' "
    else:
        bppml_command+=" modelA=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne1)))\' "
        bppml_command+=" modelC=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne2)))\' "
        bppml_command+=" modelOC=\'OneChange(model=$(modelC))\' "

    bppml_command += " \'nonhomogeneous.root_freq=FromModel(model=$(modelA))\' "

    if nodesWithAncestralModel:
        number_of_models +=1
        bppml_command+=" model%s=\'$(modelA)\' " %(number_of_models)
        bppml_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithAncestralModel)))

    if nodesWithConvergentModel:
        number_of_models +=1
        bppml_command+=" \'model%s=Mixture(model1=$(modelA),model2=$(modelC),relproba1=0.7)\' " %(number_of_models)
        bppml_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithConvergentModel)))

    if nodesWithTransitions:
        number_of_models +=1
        # Mixture
        bppml_command+=" \'model%s=Mixture(model1=$(modelA),model2=$(modelC),model3=$(modelOC),relproba1=0.7,relproba2=0.2)\' " %(number_of_models)
        bppml_command+=" model%s.nodes_id=\'%s\' " %(number_of_models,",".join(map(str, nodesWithTransitions)))
    
    paths_option_str = ""
    if number_of_models == 3: # 2 Mixture models
        paths_option_str+=" site.number_of_paths=2 "
        paths_option_str+=" site.path1=\'model2[2] & model3[2] & model3[3]\' "

    gamma_option_str = ""
    if gamma:
        gamma_option_str+=" rate_distribution=\'Gamma(n=4)\' "
    elif inv_gamma:
        gamma_option_str+=" rate_distribution=\'Invariant(dist=Gamma(n=4))\' "
    else:
        gamma_option_str+=" rate_distribution=\'Constant()\' "
    
    max_gap_allowed_option_str = ""
    if 0 <= max_gap_allowed <=100:
        max_gap_allowed_option_str+=" input.sequence.max_gap_allowed=%s " %(max_gap_allowed)
    else:
        logger.error("max_gap_allowed (%s) must be between 0 and 100", max_gap_allowed)
        sys.error(1)
    
    bppml_command += max_gap_allowed_option_str + gamma_option_str + paths_option_str

    bppml_command += "nonhomogeneous.number_of_models=%s " %(number_of_models)

    if debug_mode_bpp:
        logger.debug("%s", bppml_command)

    out_bppml = commands.getoutput(bppml_command)

    if debug_mode_bpp:
        logger.info("%s\n%s", out_bppml, bppml_command)

    if re.search("^Number of sites retained.*: 0$",out_bppml,re.MULTILINE) or \
        re.search("^Number of sites.*: 0$",out_bppml,re.MULTILINE):
        logger.warning("No site retained for %s (too much gaps), you can use the \"--max_gap_allowed\" option.", name)
        f_infos = open(output_infos_bppml,"w")
        f_infos.close()

    if not os.path.exists(output_infos_bppml):
        logger.error("%s does not exist", output_infos_bppml)
        logger.error("bppml_command: %s\nout:\n%s", bppml_command, out_bppml)
        sys.exit(42)
    
    ### bppmixedlikelihoods ###
    output_infos_bppmixedl =  "%s/%s_%s_%s%s.bppmixedl.infos"  %(repest, name , c1, c2, suffix)

    bppmixedl_command  = "bppmixedlikelihoods input.sequence.remove_saturated_sites=yes input.sequence.sites_to_use=all alphabet=Protein input.tree.format=Nhx "
    bppmixedl_command += " output.likelihoods.file=%s likelihoods.model_number=%s " %(output_infos_bppmixedl, number_of_models)
    bppmixedl_command += " param=%s input.tree.file=%s input.sequence.file=%s " %(output_params_bppml, tree_fn, fasta_fn)
    bppmixedl_command += max_gap_allowed_option_str + gamma_option_str + paths_option_str
    
    out_bppmixedl = commands.getoutput(bppmixedl_command)

    if debug_mode_bpp:
        logger.info("%s\n%s", out_bppmixedl, bppmixedl_command)
    
    if not os.path.exists(output_infos_bppmixedl):
        logger.error("%s does not exist", output_infos_bppmixedl)
        logger.error("command bppml: %s\nout:\n%s", bppml_command, out_bppml)
        logger.error("command bppmixedlikelihoods: %s\nout:\n%s", bppmixedl_command, out_bppmixedl)
        sys.exit(42)


    ### Read outputs ###
    logger.info("Read and save likelihoods (mixture) (%s, %s)", c1, c2)
    ## bppml ##
    df_bppml = pd.read_csv(output_infos_bppml, sep = '\s+', names = ["Sites", "is.complete", "is.constant", "LG", "rc", "pr"], header = 0)
    logger.debug("bppml: %s", df_bppml.to_string() )
    ## bppmixedlikelihoods ##
    df_bppmixedl = pd.read_csv(output_infos_bppmixedl, sep = '\s+', names = ["Sites", "LMa", "LMpc", "LMpcoc"], header = 0)
    logger.debug("bppmixedlikelihoods: %s", df_bppmixedl.to_string() )
    
    df_c1c2 = pd.merge(df_bppml[["Sites", "LG"]], df_bppmixedl, on = "Sites")

    df_c1c2["lnl_Ma"] = df_c1c2["LG"] + df_c1c2["LMa"]  #(product of ln * -> +)
    df_c1c2["lnl_Mpc"] = df_c1c2["LG"] + df_c1c2["LMpc"]
    df_c1c2["lnl_Mpcoc"] = df_c1c2["LG"] + df_c1c2["LMpcoc"]
    
    df_c1c2["C1"] = c1
    df_c1c2["C2"] = c2
    df_c1c2["Sites"] = df_c1c2["Sites"].str.replace("[","").str.replace("]","")
    df_c1c2["Sites"] = pd.to_numeric(df_c1c2["Sites"])
    
    return(df_c1c2)

def make_estim_conv(name, c1, g_tree, est_profiles, suffix="", gamma = False, max_gap_allowed=90):

    repseq        = g_tree.repseq
    repest        = g_tree.repest
    repbppconfig  = g_tree.repbppconfig

    tree_fn       = g_tree.treeconv_fn_est

    allNodes = [n.ND for n in g_tree.tree_conv_annotated.traverse() if not n.is_root()]
    logger.debug(allNodes)

    fasta_file = "%s/%s%s" %(repseq, name, ".fa")
    if not os.path.isfile(tree_fn):
        logger.error("%s is not a file", tree_fn)
    if not os.path.isfile(fasta_file):
        logger.error("%s is not a file", fasta_file)

    output_infos  = "%s/%s_topo%s.infos"   %(repest, name, suffix)
    output_params = "%s/%s_topo%s.params" %(repest, name, suffix)

    command="bppml param=%s \'optimization.ignore_parameters=*\' output.infos=%s output.estimates=%s input.tree.file=%s \'input.sequence.file=%s\' "%(repbppconfig + "/CATseq_conv.bpp", output_infos, output_params, tree_fn, fasta_file)
    number_of_models = 0

    if est_profiles.name in ["C10","C60"]:
        command += " NBCAT=%s " %(est_profiles.nb_cat)
    else:
        if not os.path.isfile(est_profiles.formatted_frequencies_filename):
            logger.error("%s is not a file", est_profiles.formatted_frequencies_filename)
        command += " PROFILE_F=%s " %(est_profiles.formatted_frequencies_filename)

    command += " Ne1=%d " %(c1)

    if est_profiles.name in ["C10","C60"]:
        command+=" modelA=\'LGL08_CAT_C%s(nbCat=$(NBCAT))\' " %(c1)
    else:
        command+=" modelA=\'LG08+F(frequencies=Empirical(file=$(PROFILE_F), col=$(Ne1)))\' "

    command += " \'nonhomogeneous.root_freq=FromModel(model=$(modelA))\' "

    if allNodes:
        number_of_models +=1
        command+=" model%s=\'$(modelA)\' " %(number_of_models)
        command+=" model%s.nodes_id=\'%s\' " %(number_of_models,"\'"+ ",".join(map(str, allNodes))+"\'")

    if gamma:
        command+=" rate_distribution=\'Gamma(n=4)\' "
    else:
        command+=" rate_distribution=\'Constant()\' "

    if 0 <= max_gap_allowed <=100:
        command+=" input.sequence.max_gap_allowed=%s " %(max_gap_allowed)
    else:
        logger.error("max_gap_allowed (%s) must be between 0 and 100", max_gap_allowed)
        sys.error(1)

    command += " nonhomogeneous.number_of_models=%s " %(number_of_models)

    out = commands.getoutput(command)

    if debug_mode_bpp:
        logger.debug("%s\n%s\n%s", command, out, command)

    if re.search("^Number of sites retained.*: 0$",out,re.MULTILINE) or \
       re.search("^Number of sites.*: 0$",out,re.MULTILINE):
        logger.warning("No site retained for %s", output_infos)
        f_infos = open(output_infos,"w")
        f_infos.close()


########################################################################
##                     Configuration files                            ##
########################################################################

#==> CATseq_estim.bpp <==
CATseq_estim= """alphabet=Protein
input.tree.format=Nhx
input.sequence.sites_to_use=all
nonhomogeneous = general
### estimation
input.sequence.remove_saturated_sites=yes
"""

#==> CATseq_conv.bpp <==
CATseq_conv_bpp = """alphabet=Protein
input.tree.format=Nhx
input.sequence.sites_to_use=all
nonhomogeneous = general
### estimation
input.sequence.remove_saturated_sites=yes
"""

#==> CATseq_sim.bpp <==
CATseq_sim_bpp = """alphabet=Protein
input.tree.format=Nhx
nonhomogeneous = general
"""
