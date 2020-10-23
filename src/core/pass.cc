/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 * 
 *   http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/*!
 *  Copyright (c) 2016 by Contributors
 * \file pass.cc
 * \brief Support for pass registry.
 */
#include <cvm/pass.h>
#include <algorithm>

namespace utils {
// enable registry
CVMUTIL_REGISTRY_ENABLE(cvm::PassFunctionReg);
}  // namespace utils

namespace cvm {

const PassFunctionReg* FindPassDep(const std::string&attr_name) {
  for (auto* r : utils::Registry<PassFunctionReg>::List()) {
    for (auto& s : r->graph_attr_targets) {
      if (s == attr_name) return r;
    }
  }
  return nullptr;
}

Graph ApplyPasses(Graph g,
                  const std::vector<std::string>& pass) {
  std::vector<const PassFunctionReg*> fpass;
  std::unordered_map<const PassFunctionReg*, std::string> idicator;
  for (auto& name : pass) {
    auto* reg = utils::Registry<PassFunctionReg>::Find(name);
    CHECK(reg != nullptr)
        << "Cannot find pass " << name << " in the registry";
    fpass.push_back(reg);
    idicator[reg] = name;
  }

  for (auto r : fpass) {
    // std::cout << "Apply pass [" << idicator[r]
    //   << "] with attrs: ";
    // for (auto p : g.attrs) std::cout << p.first << " ";
    // std::cout << "\n";

    for (auto& dep : r->graph_attr_dependency) {
      if (g.attrs.count(dep) == 0) {
        auto* pass_dep = FindPassDep(dep);
        std::string msg;
        if (pass_dep != nullptr) {
          msg = " The attribute is provided by pass " + pass_dep->name;
        }
        LOG(FATAL) << "Graph attr dependency " << dep
                   << " is required by pass " << r->name
                   << " but is not available "
                   << msg;
      }
    }
    g = r->body(std::move(g));
  }

  return g;
}

}  // namespace cvm
