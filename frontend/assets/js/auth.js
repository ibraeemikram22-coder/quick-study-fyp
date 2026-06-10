const API_BASE = "http://127.0.0.1:5000/auth";

function openModal(){
  document.getElementById("authModal").style.display="flex";
}

function closeModal(){
  document.getElementById("authModal").style.display="none";
}

function loginUser(){
  const email = loginEmail.value;
  const password = loginPassword.value;

  fetch(`${API_BASE}/login`,{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body:JSON.stringify({email,password})
  })
  .then(r=>r.json())
  .then(d=>{
    if(d.error) alert(d.error);
    else{
      localStorage.setItem("user_email",email);
      closeModal();
    }
  });
}

function signupUser(){
  fetch(`${API_BASE}/signup`,{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body:JSON.stringify({
      email: signupEmail.value,
      password: signupPassword.value
    })
  })
  .then(r=>r.json())
  .then(d=>{
    alert(d.message || d.error);
    if(d.message) showLogin();
  });
}


